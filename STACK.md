# hyper-ambient — runtime stack

Decisions, and the reason each one is the way it is. Numbers in this file come
from measurements on the target machine (RTX 4070 12 GB, 20 vCPU, WSL2), not
from vendor claims. Anything not yet measured is marked `[À VÉRIFIER]`.

## 0. Current model card (source of truth)

<!-- carte-figee:debut -->

The source of truth is `dev/scripts/carte_figee.env`. It is loaded by the
host-agent (`charger_carte_figee` in `dev/scripts/serve_hostagent.py`) and
followed by `dev/scripts/fetch_models.sh`, which fetches the weights it names.
Disable it with `CARTE_FIGEE=0`. Frozen on 19 September 2026, after blind
listening and measurement on the target machine.

| Role | Model | Runtime / where |
|---|---|---|
| BRAIN, local reflex | Granite 4.2 3B, GGUF Q4_K_M (`granite-4.2-3b-Q4_K_M.gguf`), alias `mother-local` | llama-server, CUDA, container port 8080 (host 8090) |
| BRAIN, remote escalation | `router` decides each turn with a local classifier; escalates to `MiniMaxAI/MiniMax-M3` | OpenAI-compatible endpoint (`BRAIN_API_ENDPOINT`, `BRAIN_API_KEY` in `.env.local`) |
| EARS | faster-whisper `large-v3`, `int8_float16`, French, hotwords `Hyper Ambient` | CTranslate2, cuda |
| MOUTH | Magpie (NeMo-Speech.cpp), voice `Sofia`, French, output gain 9 dB | NeMo-Speech.cpp + GGUF, cuda |

```env
BRAIN_SERVICE=router
BRAIN_MODEL=MiniMaxAI/MiniMax-M3
BRAIN_MODEL_LOCAL=mother-local
MODEL=/workspace/models/gguf/granite-4.2-3b-Q4_K_M.gguf
EARS_BACKEND=faster-whisper
EARS_MODEL=large-v3
EARS_LANGUAGE=fr
EARS_DEVICE=cuda
EARS_COMPUTE_TYPE=int8_float16
EARS_HOTWORDS=Hyper Ambient
MOUTH_BACKEND=magpie
MOUTH_VOICE_NAME=Sofia
MOUTH_LANGUAGE=fr
MOUTH_DEVICE=cuda
MOUTH_OUTPUT_GAIN_DB=9
```

<!-- carte-figee:fin -->

**Mac profile.** `packaging/macos/mac-16g.env.example` (profile
`mac-16g-voix-max`) is the Apple Silicon profile. It does not contradict the
card: it runs without CUDA, so it uses other engines. BRAIN local is
`mlx-community/LFM2.5-8B-A1B-OptiQ-4bit` via MLX-LM, EARS is Qwen3-ASR MLX, and
MOUTH is Chatterbox MLX. Its weights are pinned in
`packaging/macos/models.lock.json`, and its install steps are in
`packaging/macos/README.md`. The card above is the Windows/WSL2 RTX 4070 target.

**Superseded (history and fallbacks only, not current).** LFM2.5-2.6B (local
BRAIN from 2026-09-02 until the card; still the fallback GGUF in
`serve_llama.sh`), Luth-2-2B (earlier default, fallback), Ministral-3-8B and
Luciole-8B (evaluated, §2), MiniCPM5-2B (earlier default in `.env.example`),
Pocket TTS with voice `estelle` (earlier MOUTH), Piper (earlier CPU MOUTH, still
downloaded as a fallback), faster-whisper `large-v3-turbo` (earlier EARS, still
downloaded as a fallback), StepFun `step-3.7-flash` (retired: its account
answers HTTP 402 quota_exceeded, see §1), Qwen3-ASR (earlier EARS; only the Mac
profile uses an MLX variant), Supertonic (earlier MOUTH candidate), and
Qwen3-TTS (rejected, §2).

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
   │ input.inject  │    │   │ BRAIN  │ ──HTTP/SSE──────┼──▶ router → MiniMax-M3 (remote)
   │ surface.draw  │    │   │ MOUTH  │ Magpie Sofia    │      or
   └───────────────┘    │   │ACOUSTIC│ pyloudnorm      │  llama-server :8080
        WebSocket :8001 │   └────────┘                 │  (Granite 4.2 3B, CUDA)
                        │        │                     │
                        │      GATE  ── audit log ──┐  │
                        └──────────────────────────────┘
```

The consequence that matters: **BRAIN's local and remote deployments are the
same code path.** `llama-server` exposes `/v1/chat/completions` with SSE
framing identical to the remote endpoint's. `src/brain/openai_compat.py` drives
both; `src/brain/factory.py` picks one from `BRAIN_SERVICE` (default `router`,
which sends each turn local or remote). The fallback wrapper
(`build_brain_with_fallback`) exists because of the StepFun 402 case: a remote
that answers healthy but refuses every completion with a quota error.

That is why BRAIN is a *degradable* dependency rather than a hard one.

---

## 2. Per-capability choices

| Capability | Runtime | Where | Why this one |
|---|---|---|---|
| **EARS** | `faster-whisper` (CTranslate2), `large-v3`, `int8_float16` | GPU | Chosen with the card (19 Sept 2026). Quantised runtime, no Python in the decode loop. `int8_float16` halves VRAM vs `float16` (measured on `large-v3-turbo`, historical, §4). whisper.cpp (GGUF) is the ggml sibling and stays as a fallback: same tooling, same quantisation vocabulary as llama.cpp. |
| **TURN** | `silero-vad` (ONNX) — **L1** | CPU | 512-sample frames, ~1 ms each. Acoustic only: it knows sound stopped, not that a thought finished. |
| **TURN** | Pipecat Smart Turn — **L2** | GPU | Semantic endpointing. Still the open risk (OQ-15): L1 exists precisely so TURN has no single-component dependency. |
| **MOUTH** | Magpie (NeMo-Speech.cpp), voice `Sofia` | GPU | Chosen with the card (19 Sept 2026), after blind listening; output gain +9 dB. Piper (ONNX VITS, CPU, RTF 0.03) was the earlier choice; it left the GPU alone, see history below. |
| **BRAIN** | llama.cpp `llama-server` (Granite 4.2 3B Q4_K_M, alias `mother-local`) / `router` → MiniMax-M3 | GPU / remote | See §0 and §1. |
| **ACOUSTIC** | `pyloudnorm` (EBU R128) + librosa descriptors | CPU | Descriptors only, no model. |
| **GATE** | in-process, hash-chained audit log | — | Single permission control point; every capability decision is appended and chain-verified. |

#### History: rejected for MOUTH in the Piper era — Qwen3-TTS-12Hz-1.7B via `llama-tts`

Tested, measured, rejected. Qwen advertises 97 ms first-packet streaming, but
that comes from their dual-track architecture, which llama.cpp's `llama-tts`
does not implement — it generates every frame, then runs the vocoder
(`generation 1.64s + vocoder 0.05s`).

| | Piper (then) | Qwen3-TTS via llama-tts |
|---|---|---|
| RTF | **0.03** | 0.21 – 0.30 |
| Streaming | per clause | none |
| Server | in-process | none — one-shot CLI, ~6 s model load per call |
| First audio | **102 ms** | 1040 ms (whole sentence) |

Making it viable would mean writing a persistent server around `libmtmd`, and
even then a sentence costs 1.7 s. Kept on disk for offline/voice-cloning use
(24 kHz, 3-second clone), out of the realtime path.

**The lesson, which still holds: MOUTH latency was never bound by synthesis
speed.** Piper was already 30x realtime. TTFA is set by *how much text we wait
for before starting* — see `synthesize_stream`'s word-boundary cut, which took
the measured round-trip from 911 ms to 500 ms without changing the model.

### Local BRAIN candidates, measured (historical, before the card)

Same prompts, same server flags, French voice system prompt, `temperature=0.2`.
This is the LFM2.5-era bench. It has no row for Granite 4.2 3B, the card's
local BRAIN, so Granite's figures are `[À VÉRIFIER]`.

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

**Selected today: Granite 4.2 3B Q4_K_M (alias `mother-local`)**, per the card
in §0 (frozen 19 Sept 2026). Its TTFT, throughput and VRAM are `[À VÉRIFIER]`.

Earlier selections: LFM2.5-2.6B-Q5_K_M (alias `mother-local` on :8090), chosen
2026-09-02 to replace Luth-2-2B. The table above is that round's data. It held
high throughput, low TTFT (~26-38 ms) and a compact VRAM footprint (~1.9 GB).
Luth-2-2B was the default before that. Ministral-3-8B was the documented depth
swap.

**French-native pretraining did not win.** Luciole-8B (OpenLLM-France, ~30 %
French corpus) is the worst of the five here: 3× the TTFT, the only one still
emitting markdown despite the voice prompt, and the furthest off on arithmetic.
Sovereign pretraining does not convert into voice-assistant behaviour at this
scale.

**The arithmetic column is the honest cost of the no-reasoning rule.** The task
("il est 14 h 40, réunion dans 20 min, durée 40 min") needs two chained steps;
**all five** non-reasoning models in this round answer 15 h 20 instead of
15 h 40 — 0/5 each. An earlier 2/5 for LFM2.5 was prompt noise and did not
survive a controlled re-run. No prompt fixed it. This is not a model-selection
problem to keep shopping for: it is the trade the latency budget bought.
Multi-step turns belong on the deep tier, routed there deliberately.

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

The card (Granite 4.2 3B Q4_K_M, large-v3 int8_float16, Magpie Sofia) has no
VRAM measurement in the repo yet: `[À VÉRIFIER]`. The rows below come from the
previous stack (LFM2.5-2.6B, large-v3-turbo, Piper) and are kept as history.

| Component | Card (current) | History (previous stack) |
|---|---|---|
| BRAIN — Granite 4.2 3B `Q4_K_M` | `[À VÉRIFIER]` | — |
| BRAIN — LFM2.5-2.6B `Q5_K_M` + 8k ctx (KV q8_0) | — | **~1.9 GB** (measured) |
| EARS — `large-v3` int8_float16 | `[À VÉRIFIER]` | — |
| EARS — `large-v3-turbo` int8_float16 | — | ~1.6 GB (estimate) |
| MOUTH — Magpie Sofia | `[À VÉRIFIER]` | — |
| MOUTH — Piper | — | 0 (CPU) |
| TURN-L1 — Silero | 0 (CPU) | 0 (CPU) |
| planned: MOUTH — Qwen3-TTS-12Hz-1.7B `Q4_K_M` + mmproj (rejected, §2) | — | ~1.4 GB |
| planned: TURN-L2 | — | ~0.5 GB |
| headroom | `[À VÉRIFIER]` | ~4.5 GB (estimate) |

Measured free VRAM with Luth loaded and the Windows desktop up: **7996 MiB**
(measurement dated 2026-08-21, when Luth-2-2B was still the default BRAIN —
historical, not a reading of the current stack).
In that setup, everything planned above fit with room to spare.

Choosing an 8 B instead (Ministral, 5.4 GB) left ~2.6 GB in that setup — enough
for EARS *or* the new TTS, not both. That was the trade the benchmark in §2
resolved in favour of the 2 B.

---

## 4. Latency budget (NFR-01: perceived round-trip < 1200 ms)

The figures below are historical: one measurement of the previous stack (LFM2.5-2.6B,
large-v3-turbo, Piper), full chain, French, 4.26 s spoken question (`make demo`
with `--audio`). The card's column is `[À VÉRIFIER]` until it is measured on
this machine.

| Stage | Card (current) | History (previous stack) | Notes |
|---|---|---|---|
| TURN endpoint decision | same component (Silero, CPU), not re-measured | **20 ms** compute, RTF 0.004 | endpoint at 4.30 s |
| EARS transcription | `[À VÉRIFIER]` | **370 ms**, RTF 0.087 | GPU, `large-v3-turbo` int8_float16 (card: `large-v3`) |
| BRAIN time-to-first-token | `[À VÉRIFIER]` | **27 ms** | LFM2.5-2.6B Q5_K_M (`mother-local` :8090), CUDA |
| MOUTH time-to-first-audio | `[À VÉRIFIER]` | **102 ms** | Piper, CPU, word-bounded opening |
| **perceived round-trip** | `[À VÉRIFIER]` | **500 ms** | budget 1200 ms — historically within, 2.4x margin |
| full generation | — | 16.5 s | 8.8 s of speech, 2 chunks |
| EARS accuracy | `[À VÉRIFIER]` | WER 2.6 % | closed-loop Piper→Whisper; the only error is `un`→`1` |
| BRAIN TTFT (StepFun) | retired | not measurable | key valid (`/v1/models` 200), account 402 quota_exceeded |

Perceived round-trip is what the pipeline overlaps for: `PiperTTS.synthesize_stream`
consumes BRAIN's token deltas and synthesises **per sentence**, so the user
hears sentence 1 while BRAIN is still generating sentence 3. The same overlap
applies to the card's Magpie path. Perceived round-trip is therefore

```
EARS_transcribe + BRAIN_TTFT + MOUTH_first_sentence
```

not the sum of the full generations. `dev/scripts/pipeline_demo.py` prints this
breakdown and flags over-budget.

Historically, EARS was the dominant cost (370 of 500 ms) and Voxtral-Mini-4B-Realtime
(natively streaming, 240 ms–2.4 s configurable delay, Apache-2.0) was the
candidate to attack it. In a later run MOUTH was the dominant cost (515 of
912 ms), which §2 explains as structural rather than a tuning problem.

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
| 8091 | 8081 | `whisper-server` (whisper.cpp, fallback) |

---

## 7. Build layering

`requirements.txt` and the torch install are **never touched** by the extras.
Everything added later lives in appended layers (`requirements-extra.txt`,
llama.cpp, whisper.cpp), so a rebuild reuses the CUDA base image and the torch
wheels from cache — no re-download of the 2.65 GB base or the multi-GB torch
stack.

Model weights live in `./models`, a host bind-mount, so they survive image
rebuilds entirely.
