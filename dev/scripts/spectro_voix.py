"""Mesures stereo + spectrogrammes. Script separe pour eviter les pannes ffmpeg/wave."""
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path("/workspace/data/voix")
OUT = ROOT / "_listen"
OUT.mkdir(exist_ok=True)


def main() -> None:
    x, sr = sf.read(ROOT / "aurora_ref.m4a", always_2d=True)
    print("aurora_ref.m4a", x.shape, sr, x.dtype)
    L, R = x[:, 0], x[:, min(1, x.shape[1] - 1)]
    mid = (L + R) / 2
    side = (L - R) / 2
    e_mid = float(np.mean(mid ** 2))
    e_side = float(np.mean(side ** 2))
    corr = float(np.corrcoef(L, R)[0, 1]) if x.shape[1] > 1 else 1.0
    print(f"corr={corr:.3f} side/mid={e_side / max(e_mid, 1e-12):.3f}")

    n = min(len(mid), sr * 8)
    spec = np.abs(np.fft.rfft(mid[:n] * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1 / sr)

    def be(lo: float, hi: float) -> float:
        m = (fr >= lo) & (fr < hi)
        return float(np.mean(spec[m] ** 2))

    voice, low, sibil, air = be(200, 4000), be(40, 120), be(5000, 8000), be(8000, min(12000, sr / 2 - 1))
    print(f"voice={voice:.3e} low={low:.3e} sibil={sibil:.3e} air={air:.3e}")
    print(f"air/voice={air / max(voice, 1e-18):.4f} low/voice={low / max(voice, 1e-18):.4f}")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = {
        "aurora": ROOT / "ref_aurora_24k.wav",
        "eponine": ROOT / "pocket_eponine_fr.wav",
        "alba": ROOT / "pocket_alba_fr.wav",
        "estelle": ROOT / "pocket_estelle_fr.wav",
        "supertonic_f5": ROOT / "supertonic_f5_fr.wav",
        "siwis_flat": ROOT / "piper_siwis-flat_fr.wav",
        "siwis_mother": ROOT / "piper_siwis-mother_fr.wav",
    }
    fig, axes = plt.subplots(len(files), 1, figsize=(12, 2.2 * len(files)))
    for ax, (name, path) in zip(axes, files.items()):
        y, s = sf.read(path)
        if y.ndim > 1:
            y = y.mean(axis=1)
        ax.specgram(y, NFFT=1024, Fs=s, noverlap=768, cmap="magma")
        ax.set_ylim(0, 8000)
        ax.set_title(name)
        ax.set_ylabel("Hz")
    axes[-1].set_xlabel("s")
    fig.tight_layout()
    dest = OUT / "spec_compare.png"
    fig.savefig(dest, dpi=130)
    print("wrote", dest)


if __name__ == "__main__":
    main()
