from pathlib import Path
import wave
import numpy as np
from faster_whisper import WhisperModel
from src.mouth.voice_design import AURORA, VoiceTreatment

VOIX = Path("/workspace/data/voix")


def lire(p):
    with wave.open(str(p), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    return x / 32768.0, sr


def f0_med(x, sr):
    n = int(sr * 0.04)
    lo, hi = int(sr / 400), int(sr / 70)
    vals, rms = [], float(np.sqrt(np.mean(x ** 2)))
    for i in range(0, len(x) - n, n):
        b = x[i : i + n] - x[i : i + n].mean()
        if float(np.sqrt(np.mean(b * b))) < rms * 0.4:
            continue
        ac = np.correlate(b, b, "full")[n - 1 :]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        p = lo + int(np.argmax(ac[lo:hi]))
        if ac[p] < 0.3:
            continue
        vals.append(sr / p)
    return float(np.median(vals)) if vals else 0.0


def centroid(x, sr):
    n = 2048
    w = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    c = 0
    for i in range(0, len(x) - n, n // 2):
        mag = np.abs(np.fft.rfft(x[i : i + n] * w))
        if mag.sum() < 1e-6:
            continue
        acc += mag
        c += 1
    if not c:
        return 0.0
    acc /= c
    fr = np.fft.rfftfreq(n, 1 / sr)
    return float(np.sum(fr * acc) / np.sum(acc))


x, sr = lire(VOIX / "qwen3tts_aurora_fr.wav")
pcm = np.clip(x * 32767, -32768, 32767).astype(np.int16)
treated = VoiceTreatment(AURORA, sr).process(pcm)
with wave.open(str(VOIX / "qwen3tts_aurora_treated_fr.wav"), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(treated.tobytes())

print(f"clone {len(x)/sr:.2f}s  f0={f0_med(x,sr):.1f}  cent={centroid(x,sr):.0f}")
xt, _ = lire(VOIX / "qwen3tts_aurora_treated_fr.wav")
print(f"treated          f0={f0_med(xt,sr):.1f}  cent={centroid(xt,sr):.0f}")

m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
for n in ["qwen3tts_aurora_fr.wav", "qwen3tts_aurora_treated_fr.wav", "qwen3tts_aurora_leak_fr.wav"]:
    segs, info = m.transcribe(str(VOIX / n), language=None)
    texte = " ".join(s.text.strip() for s in segs)
    print(f"ASR {n} lang={info.language} p={info.language_probability:.2f}")
    print(" ", texte)
