# Critical Measurements for MOTHER

These measurements **must** be completed on the dev machine before finalizing architecture.

## 1. `rtf_whisper.cpp` — Real-Time Factor (EARS-L1)

**What**: How fast is ASR relative to audio duration?
- RTF < 1.0 → can keep up with real-time speech
- RTF = 1.0 → same speed as real time
- RTF > 1.0 → slower than real time (needs buffering/lag)

**Procedure**:
- Load `whisper.cpp` with `tiny` quantized model
- Feed 30 minutes of continuous French audio (mixed speakers, including accented variants, background noise)
- Measure wall-clock time from first audio frame to last result
- RTF = wall_clock_time / audio_duration
- Target: RTF < 1.5 (allows 33% latency budget for other capabilities)

**Corpus**: See `dev/data/` — must include:
  - News/audiobook (clean speech)
  - Conversation (overlapping speakers, interruptions)
  - Noisy environment (traffic, kitchen sounds)
  - Regional accents (Quebec, Belgian, Swiss French)

**Blocker**: If RTF > 3.0 on this machine, PROFILE_MEDIUM config is compromised.

---

## 2. `false_endpoint_rate` of Pipecat Smart Turn v3.2 (TURN-L2)

**What**: How often does TURN predict a break when the speaker is still talking?

**Procedure** (see `benchmark-protocol.md` § benchmark cases A01–A04):
- Adversarial corpus: false breaks are inserted at known positions
  - A01: Speaker pauses mid-sentence (1–3 sec), resumes
  - A02: Filled pauses (uh, euh, hm) followed by speech
  - A03: Overlapping speech (two speakers simultaneously)
  - A04: Long silence after question (5–10 sec), response coming
- For each audio, record:
  - Endpoints predicted by Pipecat
  - Ground truth (where actual speaker transitions occur)
  - False positives (predicted break when speaker didn't stop)
  - False negatives (missed actual break)
- Calculate: FPR = false_positives / (false_positives + true_negatives)

**Blocker**: If FPR > 0.15 (15% false break rate), ADR-001 is at risk — we need a fallback to VAD-only.

**Note**: OQ-15 tracks this. If measurement fails, TURN reverts to L1 (VAD fallback only).

---

## 3. `ttfa_perceived` — Time-To-First-Audio, Perceived (MOUTH-L2)

**What**: How long does a human wait to hear the first syllable of synthesis output?

**Procedure**:
- Load Pocket TTS with French model
- Provide short text prompt ("Bonjour", "Je suis MOTHER")
- Measure from input trigger to **first audible sound** in actual audio buffer (not wall-clock inference)
- Repeat 10 times, report min/median/max
- Hardware: Use real loopback cable (USB audio interface or internal loopback)
- Metric: `ttfa_perceived_ms` (not inference time, actual latency heard by user)

**Target**: < 300 ms (current spec claim: 200 ms)

**Notes**:
- Pocket TTS publishes 200 ms, but measurement doesn't declare start/end points
- We must verify on the actual dev machine because TTS latency is hardware-dependent
- If MOSS-TTS is significantly faster, it becomes the preferred candidate

**Blocker**: If TTFA > 500 ms, NFR-01 (round-trip latency < 1200 ms) is at risk.

---

## Files to Create

- `whisper_benchmark.py` — script to load whisper.cpp and measure RTF
- `pipecat_turn_eval.py` — script to load Pipecat and evaluate FPR on corpus A01–A04
- `pocket_tts_latency.py` — script to measure TTFA with audio loopback

## Timeline

Run in parallel:
- [ ] Download corpus (30 min)
- [ ] Set up audio loopback (10 min)
- [ ] Run whisper RTF benchmark (1 hour)
- [ ] Run Pipecat turn evaluation (30 min)
- [ ] Run Pocket TTS latency (15 min)

**Total**: ~2 hours (parallelizable)

Once results are in, validate against thresholds and decide:
- If all pass: proceed to full implementation
- If one fails: activate contingency (e.g., switch to MOUTH candidate, use VAD-only for TURN)
