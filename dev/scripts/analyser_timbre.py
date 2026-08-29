"""Analyse acoustique de la reference Aurora et des candidats TTS."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

TMP = Path("/tmp/listen/_tmp.wav")
TMP.parent.mkdir(parents=True, exist_ok=True)


def load(path: str, sr: int = 24000) -> tuple[np.ndarray, int]:
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", str(sr), str(TMP)],
        capture_output=True,
        check=True,
    )
    with wave.open(str(TMP), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return x, sr


def f0_stats(x: np.ndarray, sr: int) -> tuple[float, float, float]:
    n = int(sr * 0.04)
    lo, hi = int(sr / 400), int(sr / 70)
    vals = []
    rms = float(np.sqrt(np.mean(x ** 2)))
    for i in range(0, len(x) - n, n):
        b = x[i : i + n]
        b = b - b.mean()
        e = float(np.sqrt(np.mean(b * b)))
        if e < rms * 0.4:
            continue
        ac = np.correlate(b, b, "full")[n - 1 :]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        p = lo + int(np.argmax(ac[lo:hi]))
        if ac[p] < 0.3:
            continue
        vals.append(sr / p)
    if not vals:
        return 0.0, 0.0, 0.0
    h = np.array(vals)
    return float(np.median(h)), float(np.percentile(h, 25)), float(np.percentile(h, 75))


def centroid(x: np.ndarray, sr: int) -> float:
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
    if c == 0:
        return 0.0
    acc /= c
    freqs = np.fft.rfftfreq(n, 1 / sr)
    return float(np.sum(freqs * acc) / np.sum(acc))


def formants_rough(x: np.ndarray, sr: int) -> list[int]:
    n = 2048
    w = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    c = 0
    rms = float(np.sqrt(np.mean(x ** 2)))
    for i in range(0, len(x) - n, n // 2):
        b = x[i : i + n]
        if float(np.sqrt(np.mean(b * b))) < rms * 0.5:
            continue
        acc += np.abs(np.fft.rfft(b * w))
        c += 1
    if c == 0:
        return []
    acc = np.log(acc / c + 1e-12)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    k = 15
    ker = np.hanning(k)
    ker /= ker.sum()
    sm = np.convolve(acc, ker, mode="same")
    peaks = []
    for i in range(2, len(sm) - 2):
        if freqs[i] < 200 or freqs[i] > 4500:
            continue
        if sm[i] > sm[i - 1] and sm[i] > sm[i + 1] and sm[i] > sm[i - 2] and sm[i] > sm[i + 2]:
            peaks.append((float(freqs[i]), float(sm[i])))
    peaks.sort(key=lambda t: -t[1])
    return [round(p[0]) for p in peaks[:5]]


def mel_envelope(x: np.ndarray, sr: int, bands: int = 40) -> np.ndarray:
    n = 1024
    hop = 256
    fenetre = np.hanning(n)
    trames = []
    for i in range(0, len(x) - n, hop):
        bloc = x[i : i + n]
        if np.sqrt(np.mean(bloc ** 2)) > 1e-3:
            trames.append(np.abs(np.fft.rfft(bloc * fenetre)))
    if not trames:
        return np.zeros(bands)
    moyen = np.mean(trames, axis=0)
    mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)
    frequences = np.fft.rfftfreq(n, 1.0 / sr)
    bornes = np.linspace(mel(50), mel(min(8000, sr / 2)), bands + 1)
    hertz = 700.0 * (10.0 ** (bornes / 2595.0) - 1.0)
    sortie = np.array(
        [
            moyen[(frequences >= hertz[i]) & (frequences < hertz[i + 1])].mean()
            if np.any((frequences >= hertz[i]) & (frequences < hertz[i + 1]))
            else 0.0
            for i in range(bands)
        ]
    )
    sortie = np.log(sortie + 1e-10)
    return (sortie - sortie.mean()) / (sortie.std() + 1e-10)


def main() -> None:
    files = {
        "aurora": "/workspace/data/voix/_listen/aurora_ref.mp3",
        "eponine": "/workspace/data/voix/_listen/eponine.mp3",
        "alba": "/workspace/data/voix/_listen/alba.mp3",
        "estelle": "/workspace/data/voix/_listen/estelle.mp3",
        "fantine": "/workspace/data/voix/_listen/fantine.mp3",
        "supertonic_f5": "/workspace/data/voix/_listen/supertonic_f5.mp3",
        "siwis": "/workspace/data/voix/_listen/siwis_flat.mp3",
    }
    print(f"{'name':16} {'f0':>7} {'q25':>7} {'q75':>7} {'cent':>8}  formants")
    loaded = {}
    for name, path in files.items():
        x, sr = load(path)
        loaded[name] = (x, sr)
        f0, q25, q75 = f0_stats(x, sr)
        cen = centroid(x, sr)
        fo = formants_rough(x, sr)
        print(f"{name:16} {f0:7.1f} {q25:7.1f} {q75:7.1f} {cen:8.0f}  {fo}")

    cible = mel_envelope(*loaded["aurora"])
    print("\ndistance cosinus (enveloppe mel) vs aurora")
    for name, (x, sr) in loaded.items():
        if name == "aurora":
            continue
        env = mel_envelope(x, sr)
        dist = float(np.linalg.norm(env - cible))
        print(f"  {name:16} {dist:5.2f}")

    print("\n--- stereo / musique sur le m4a original ---")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            "/workspace/data/voix/aurora_ref.m4a",
            "-ar",
            "24000",
            "/tmp/listen/aurora_st.wav",
        ],
        capture_output=True,
        check=True,
    )
    with wave.open("/tmp/listen/aurora_st.wav", "rb") as w:
        ch = w.getnchannels()
        sr = w.getframerate()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
        raw = raw.reshape(-1, ch)
    print("channels after ffmpeg decode:", ch, "shape", raw.shape)
    L, R = raw[:, 0], raw[:, 1]
    mid = (L + R) / 2
    side = (L - R) / 2
    e_mid = float(np.mean(mid ** 2))
    e_side = float(np.mean(side ** 2))
    corr = float(np.corrcoef(L, R)[0, 1])
    print(
        f"L-R corr={corr:.3f}  mid={e_mid:.6f}  side={e_side:.6f}  "
        f"side/mid={e_side / max(e_mid, 1e-12):.3f}"
    )
    n = min(len(mid), sr * 8)
    spec = np.abs(np.fft.rfft(mid[:n] * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1 / sr)

    def be(lo: float, hi: float) -> float:
        m = (fr >= lo) & (fr < hi)
        return float(np.mean(spec[m] ** 2))

    b_voice = be(200, 4000)
    b_high = be(8000, 12000)
    b_low = be(40, 120)
    b_sibil = be(5000, 8000)
    print(
        f"band voice={b_voice:.3e} low={b_low:.3e} sibil={b_sibil:.3e} air={b_high:.3e}"
    )
    print(
        f"air/voice={b_high / max(b_voice, 1e-18):.4f}  "
        f"low/voice={b_low / max(b_voice, 1e-18):.4f}"
    )

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(4, 1, figsize=(12, 10))
        for ax, name in zip(axes, ["aurora", "eponine", "alba", "estelle"]):
            x, sr = loaded[name]
            ax.specgram(x, NFFT=1024, Fs=sr, noverlap=768, cmap="magma")
            ax.set_ylim(0, 8000)
            ax.set_title(name)
            ax.set_ylabel("Hz")
        axes[-1].set_xlabel("s")
        fig.tight_layout()
        out = Path("/workspace/data/voix/_listen/spec_compare.png")
        fig.savefig(out, dpi=120)
        print("wrote", out)
    except Exception as e:
        print("matplotlib fail", type(e).__name__, e)


if __name__ == "__main__":
    main()
