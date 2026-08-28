# hyper-ambient — runtime stack

Decisions, and the reason each one is the way it is. Numbers in this file come
from measurements on the target machine (RTX 4070 12 GB, 20 vCPU, WSL2), not
from vendor claims. Anything not yet measured is marked `[À VÉRIFIER]`.

---

## 1. The organising principle: one protocol, two deployments

Every heavy component is a **server behind an HTTP protocol**, not a Python
object imported into the event loop.

```
                        ┌──────────────────────────────┐
   host-agent (native)  │  mother-core (container)     │
   Windows/macOS        │                              │
   ┌───────────────┐    │   ┌────────┐                 │
   │ audio.capture │────┼──▶│ TURN   │ silero-vad      │  CPU, RTF 0.008
   │ audio.render  │◀───┼───│ EARS   │ faster-whisper  │  GPU, CT2 int8_f16
   │ input.inject  │    │   │ BRAIN  │ ──HTTP/SSE──────┼──▶ StepFun (remote)
   │ surface.draw  │    │   │ MOUTH  │ piper (ONNX)    │      or
   └───────────────┘    │   │ACOUSTIC│ pyloudnorm      │  llama-server :8080
        WebSocket :8001 │   └────────┘                 │      (local, CUDA)
                        │        │                     │
                        │      GATE  ── audit log ──┐  │
                        └──────────────────────────────┘
```

The consequence that matters: **BRAIN's local and remote deployments are the
same code path.** `llama-server` exposes `/v1/chat/completions` with SSE
framing identical to StepFun's. `src/brain/openai_compat.py` drives both;
`src/brain/factory.py` picks one from `BRAIN_SERVICE`, and falls back from
remote to local when the remote is unreachable (which is exactly what the
StepFun 402 quota error would have triggered).

That is why BRAIN is a *degradable* dependency rather than a hard one.

---

## 2. Per-capability choices

| Capability | Runtime | Where | Why this one |
|---|---|---|---|
| **EARS** | `faster-whisper` (CTranslate2) + `whisper.cpp` (GGUF) | GPU | Quantised C++ runtime, no Python in the decode loop. `int8_float16` halves VRAM vs `float16` at ~no WER cost on `large-v3-turbo`. whisper.cpp is the ggml sibling — same tooling, same quantisation vocabulary as llama.cpp. |
| **TURN** | `silero-vad` (ONNX) — **L1** | CPU | 512-sample frames, ~1 ms each. Acoustic only: it knows sound stopped, not that a thought finished. |
| **TURN** | Pipecat Smart Turn — **L2** | GPU | Semantic endpointing. Still the open risk (OQ-15): L1 exists precisely so TURN has no single-component dependency. |
| **MOUTH** | `piper` (ONNX VITS) | CPU | 61 MB French voice, RTF 0.03, deterministic latency, and — critically — **leaves the GPU alone**. On a 12 GB card already holding Whisper + a GGUF, a GPU TTS is the wrong trade. |

#### Rejected for MOUTH: Qwen3-TTS-12Hz-1.7B via `llama-tts`

Tested, measured, rejected. Qwen advertises 97 ms first-packet streaming, but
that comes from their dual-track architecture, which llama.cpp's `llama-tts`
does not implement — it generates every frame, then runs the vocoder
(`generation 1.64s + vocoder 0.05s`).

| | Piper | Qwen3-TTS via llama-tts |
|---|---|---|
| RTF | **0.03** | 0.21 – 0.30 |
| Streaming | per clause | none |
| Server | in-process | none — one-shot CLI, ~6 s model load per call |
| First audio | **102 ms** | 1040 ms (whole sentence) |

Making it viable would mean writing a persistent server around `libmtmd`, and
even then a sentence costs 1.7 s. Kept on disk for offline/voice-cloning use
(24 kHz, 3-second clone), out of the realtime path.

**The lesson: MOUTH latency was never bound by synthesis speed.** Piper is
already 30x realtime. TTFA is set by *how much text we wait for before
starting* — see `synthesize_stream`'s word-boundary cut, which took the
measured round-trip from 911 ms to 500 ms without changing the model.
| **BRAIN** | llama.cpp `llama-server` / StepFun | GPU / remote | See §1. |
| **ACOUSTIC** | `pyloudnorm` (EBU R128) + librosa descriptors | CPU | Descriptors only, no model. |
| **GATE** | in-process, hash-chained audit log | — | Single permission control point; every capability decision is appended and chain-verified. |

### Local BRAIN candidates, measured

Same prompts, same server flags, French voice system prompt, `temperature=0.2`.

All rows measured under identical conditions: `dev/scripts/bench_brain.py`,
voice system prompt, `temperature=0.2`, same server flags, GGUF Q4_K_M
(Q5_K_M for Luth).

| Model | Params | TTFT (med) | char/s | markup | arith 5-shot | VRAM | French register |
|---|---|---|---|---|---|---|---|
| LFM2.5-VL-3B | 3 B | **26 ms** | 667 | 0/4 | 0/5 | 2.0 GB | *"Ton réunion"* — agreement error, mixes tu/vous |
| **Luth-2-2B** | 1.9 B | 38 ms | **697** | 0/4 | 0/5 | **1.5 GB** | consistent tutoiement ✔ |
| Ministral-3-8B-Instruct-2512 | 8 B | 39 ms | 331 | 0/4 | 0/5 | 5.4 GB | best depth; mixes tu/vous |
| Luciole-8B-Instruct-1.1 | 8 B | 120 ms | 341 | **2/4** | 0/5 | 5.1 GB | verbose, hedging |
| Qwen3-4B-Instruct-2507 | 4 B | 43 ms | 389 | — | 0/5 | 2.8 GB | invents |

**Selected: Luth-2-2B.** It holds an 8 B's TTFT, doubles its throughput (which
is what keeps MOUTH's audio queue from starving), is the only one of the five
that never slips register — the single defect a listener actually hears — and
costs 1.5 GB instead of 5.4. That headroom is what makes Qwen3-TTS and TURN-L2
co-tenancy possible on a 12 GB card. Ministral-3-8B stays as the documented
depth swap.

**French-native pretraining did not win.** Luciole-8B (OpenLLM-France, ~30 %
French corpus) is the worst of the five here: 3× the TTFT, the only one still
emitting markdown despite the voice prompt, and the furthest off on arithmetic.
Sovereign pretraining does not convert into voice-assistant behaviour at this
scale.

**The arithmetic column is the honest cost of the no-reasoning rule.** The task
("il est 14 h 40, réunion dans 20 min, durée 40 min") needs two chained steps;
**all five** non-reasoning models answer 15 h 20 instead of 15 h 40 — 0/5 each.
An earlier 2/5 for LFM2.5 was prompt noise and did not survive a controlled
re-run. No prompt fixed it. This is not a model-selection problem to keep
shopping for: it is the trade the latency budget bought. Multi-step turns
belong on the deep tier, routed there deliberately.

### Why llama.cpp and not vLLM / TGI / transformers

For a *real-time voice harness on one consumer GPU*, the constraint is not
throughput, it is **VRAM co-tenancy and time-to-first-token**. llama.cpp wins on
all three axes that matter here:

- **VRAM control.** `--n-gpu-layers` + quantised KV cache (`q8_0`) lets BRAIN be
  told exactly how much of the 12 GB it may take, so EARS keeps its share.
  vLLM's paged allocator wants the card to itself.
- **TTFT on batch size 1.** Continuous batching is a throughput optimisation.
  A single voice session is batch-1; the graph-level work llama.cpp does
  (flash-attn, fused kernels) is what actually moves TTFT.
- **Same runtime as EARS.** ggml powers both `llama-server` and
  `whisper-server`. One build toolchain, one quantisation format, one set of
  CUDA kernels compiled for `sm_89`.

Built here with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89` (Ada Lovelace).

---

## 3. VRAM budget (12 282 MiB total, ~9 300 MiB free with the desktop up)

| Component | Measured / estimate |
|---|---|
| BRAIN — Luth-2-2B `Q5_K_M` + 8k ctx (KV q8_0) | **1.5 GB** (measured) |
| EARS — `large-v3-turbo` int8_float16 | ~1.6 GB |
| MOUTH — Piper | 0 (CPU) |
| TURN-L1 — Silero | 0 (CPU) |
| planned: MOUTH — Qwen3-TTS-12Hz-1.7B `Q4_K_M` + mmproj | ~1.4 GB |
| planned: TURN-L2 | ~0.5 GB |
| headroom | ~4.5 GB |

Measured free VRAM with Luth loaded and the Windows desktop up: **7996 MiB**.
Everything planned above fits inside that with room to spare.

Choosing an 8 B instead (Ministral, 5.4 GB) leaves ~2.6 GB — enough for EARS
*or* the new TTS, not both. That is precisely the trade the benchmark above
resolved in favour of the 2 B.

---

## 4. Latency budget (NFR-01: perceived round-trip < 1200 ms)

Measured on this machine, full chain, French, 4.26 s spoken question
(`make demo` with `--audio`):

| Stage | Measured | Notes |
|---|---|---|
| TURN endpoint decision | **20 ms** compute, RTF 0.004 | CPU, Silero, endpoint at 4.30 s |
| EARS transcription | **370 ms**, RTF 0.087 | GPU, `large-v3-turbo` int8_float16 |
| BRAIN time-to-first-token | **27 ms** | local, Luth-2-2B Q5_K_M, CUDA |
| MOUTH time-to-first-audio | **102 ms** | CPU, Piper, word-bounded opening |
| **perceived round-trip** | **500 ms** | budget 1200 ms — **within, 2.4x margin** |
| full generation | 16.5 s | 8.8 s of speech, 2 chunks |

**EARS is now the dominant cost** (370 of 500 ms) — the next thing worth
attacking, and `Voxtral-Mini-4B-Realtime` (natively streaming, 240 ms–2.4 s
configurable delay, Apache-2.0) is the candidate.
| EARS accuracy | WER 2.6 % | closed-loop Piper→Whisper; the only error is `un`→`1` |
| BRAIN TTFT (StepFun) | not measurable | key valid (`/v1/models` 200), account 402 quota_exceeded |

**MOUTH is now the dominant cost** (515 of 912 ms). That is the next thing to
attack, and §2 explains why it is structural rather than a tuning problem.

The pipeline overlaps rather than serialises: `PiperTTS.synthesize_stream`
consumes BRAIN's token deltas and synthesises **per sentence**, so the user
hears sentence 1 while BRAIN is still generating sentence 3. Perceived
round-trip is therefore

```
EARS_transcribe + BRAIN_TTFT + MOUTH_first_sentence
```

not the sum of the full generations. `dev/scripts/pipeline_demo.py` prints this
breakdown and flags over-budget.

---

## 5. Why there is no audio device in the container

Docker Desktop on Windows exposes no ALSA device — `/dev/snd` contains only
`timer`. This is not a limitation to work around; it is the reason the
architecture has two components. Capture, render, input injection and overlay
drawing are the **native host-agent's** four primitives, reached over the
WebSocket on `:8001`. The container never touches hardware audio.

---

## 6. Ports

| Host | Container | Service |
|---|---|---|
| 8000 | 8000 | hyper-ambient core API |
| 8001 | 8001 | WebSocket — host-agent transport |
| 8090 | 8080 | `llama-server` (8080 on the host is SearXNG) |
| 8091 | 8081 | `whisper-server` |

---

## 7. Build layering

`requirements.txt` and the torch install are **never touched** by the extras.
Everything added later lives in appended layers (`requirements-extra.txt`,
llama.cpp, whisper.cpp), so a rebuild reuses the CUDA base image and the torch
wheels from cache — no re-download of the 2.65 GB base or the multi-GB torch
stack.

Model weights live in `./models`, a host bind-mount, so they survive image
rebuilds entirely.
