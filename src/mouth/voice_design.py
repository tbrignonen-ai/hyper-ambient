"""
MOUTH: voice character shaping — the MU/TH/UR treatment.

A neutral TTS voice does not read as a ship's computer. Two levers:

  1. Delivery, at synthesis time. Slower rate, flattened pitch variation and
     regularised phoneme durations make the reading unhurried and impersonal.
     These are Piper `SynthesisConfig` fields, not DSP.

  2. Space and grain, after synthesis. MOTHER speaks through a hull: band
     limiting, a short metallic room, a faint doubling.

Everything here is **stateful and streaming-safe**. Filters keep their `zi`
and the reverb keeps its buffers across calls, because MOUTH emits one chunk
per clause — a stateless implementation would click at every seam.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import signal


@dataclass
class VoiceProfile:
    """Delivery + treatment for one character."""

    # --- synthesis (Piper SynthesisConfig) ---
    length_scale: float = 1.0      # >1 speaks slower
    noise_scale: float = 0.667     # pitch/timbre variability; lower = flatter
    noise_w_scale: float = 0.8     # duration variability; lower = metronomic

    # --- treatment ---
    highpass_hz: float = 0.0       # 0 disables
    lowpass_hz: float = 0.0
    reverb_mix: float = 0.0        # 0..1
    reverb_decay: float = 0.0      # 0..1, feedback amount
    double_ms: float = 0.0         # faint delayed copy, 0 disables
    double_mix: float = 0.0
    drive: float = 1.0             # pre-limiter gain


# Neutral: whatever the voice does natively.
FLAT = VoiceProfile()

# MU/TH/UR 6000 — unhurried, level, speaking inside a metal room.
# Band limits are deliberately wide: a telephone band (300–3400) reads as
# "phone call", not "ship". Keeping lows to 90 Hz preserves the chest weight
# that makes it feel like it comes from the walls.
MOTHER = VoiceProfile(
    length_scale=1.16,
    noise_scale=0.45,
    noise_w_scale=0.55,
    highpass_hz=90.0,
    lowpass_hz=7200.0,
    reverb_mix=0.22,
    reverb_decay=0.62,
    double_ms=17.0,
    double_mix=0.16,
    drive=1.15,
)

# Colder and further away — for alerts rather than conversation.
MOTHER_ALERT = VoiceProfile(
    length_scale=1.08,
    noise_scale=0.35,
    noise_w_scale=0.45,
    highpass_hz=180.0,
    lowpass_hz=5200.0,
    reverb_mix=0.34,
    reverb_decay=0.72,
    double_ms=23.0,
    double_mix=0.22,
    drive=1.3,
)

PROFILES = {"flat": FLAT, "mother": MOTHER, "alert": MOTHER_ALERT}


class _Schroeder:
    """
    Small metallic room: 4 feedback combs in parallel, then 2 allpasses.

    Implemented as IIR sections rather than per-sample loops, because MOUTH's
    whole first-audio budget is ~100 ms and a Python sample loop would spend
    more than that on one clause. A feedback comb is exactly 1/(1 - g·z^-N)
    and an allpass (-g + z^-N)/(1 - g·z^-N), so `lfilter` does both in one
    vectorised call and `zi` carries the tail across chunks.
    """

    # Mutually non-commensurate delays, so the tail has no ringing pitch.
    # Two sets: running one per side gives a genuinely decorrelated tail.
    # Feeding the same tail to both channels would only widen the level, not
    # the image — it would still collapse to a point between the speakers.
    COMBS_MS = (29.7, 37.1, 41.1, 43.7)
    COMBS_MS_ALT = (31.3, 35.9, 39.7, 46.1)
    ALLPASS_MS = (5.0, 1.7)
    ALLPASS_MS_ALT = (6.3, 2.3)
    ALLPASS_G = 0.5

    def __init__(self, sample_rate: int, decay: float, variant: int = 0):
        g = float(np.clip(decay, 0.0, 0.95))
        combs_ms = self.COMBS_MS_ALT if variant else self.COMBS_MS
        allpass_ms = self.ALLPASS_MS_ALT if variant else self.ALLPASS_MS

        self._combs = []
        for ms in combs_ms:
            n = max(1, int(sample_rate * ms / 1000))
            b = np.zeros(1, dtype=np.float64)
            b[0] = 1.0
            a = np.zeros(n + 1, dtype=np.float64)
            a[0], a[n] = 1.0, -g
            self._combs.append([b, a, np.zeros(n, dtype=np.float64)])

        self._allpass = []
        for ms in allpass_ms:
            n = max(1, int(sample_rate * ms / 1000))
            ag = self.ALLPASS_G
            b = np.zeros(n + 1, dtype=np.float64)
            b[0], b[n] = -ag, 1.0
            a = np.zeros(n + 1, dtype=np.float64)
            a[0], a[n] = 1.0, -ag
            self._allpass.append([b, a, np.zeros(n, dtype=np.float64)])

    def process(self, x: np.ndarray) -> np.ndarray:
        acc = np.zeros_like(x, dtype=np.float64)
        for sec in self._combs:
            b, a, zi = sec
            y, sec[2] = signal.lfilter(b, a, x, zi=zi)
            acc += y
        acc /= len(self._combs)

        for sec in self._allpass:
            b, a, zi = sec
            acc, sec[2] = signal.lfilter(b, a, acc, zi=zi)

        return acc.astype(np.float32)


class VoiceTreatment:
    """Streaming post-processor. One instance per utterance stream."""

    def __init__(self, profile: VoiceProfile, sample_rate: int):
        self.p = profile
        self.sr = sample_rate

        self._sos = []
        nyq = sample_rate / 2.0
        if profile.highpass_hz > 0:
            self._sos.append(signal.butter(2, profile.highpass_hz / nyq, "highpass", output="sos"))
        if 0 < profile.lowpass_hz < nyq:
            self._sos.append(signal.butter(4, profile.lowpass_hz / nyq, "lowpass", output="sos"))
        self._zi = [signal.sosfilt_zi(s) * 0.0 for s in self._sos]

        self._reverb = (
            _Schroeder(sample_rate, profile.reverb_decay) if profile.reverb_mix > 0 else None
        )

        n_dbl = int(sample_rate * profile.double_ms / 1000) if profile.double_ms > 0 else 0
        self._dbl_tail = np.zeros(n_dbl, dtype=np.float32) if n_dbl else None

    def process(self, pcm16: np.ndarray) -> np.ndarray:
        """Take int16 PCM, return int16 PCM of the same length."""
        if pcm16.size == 0:
            return pcm16
        x = pcm16.astype(np.float32) / 32768.0

        for i, sos in enumerate(self._sos):
            x, self._zi[i] = signal.sosfilt(sos, x, zi=self._zi[i])

        if self._dbl_tail is not None:
            n = len(self._dbl_tail)
            delayed = np.concatenate([self._dbl_tail, x[:-n]]) if n <= x.size else np.zeros_like(x)
            self._dbl_tail = x[-n:].copy() if n <= x.size else self._dbl_tail
            x = x + self.p.double_mix * delayed

        if self._reverb is not None:
            x = (1.0 - self.p.reverb_mix) * x + self.p.reverb_mix * self._reverb.process(x)

        x = np.tanh(x * self.p.drive) / np.tanh(self.p.drive)
        return np.clip(x * 32767.0, -32768, 32767).astype(np.int16)
