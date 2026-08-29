"""Isoler la voix d'Aurora et diagnostiquer le mix YouTube."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path("/workspace/data/voix")


def ffmpeg_wav(src: str, dst: Path, extra_af: str | None = None, ar: int = 24000) -> None:
    cmd = ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", str(ar)]
    if extra_af:
        cmd += ["-af", extra_af]
    cmd.append(str(dst))
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    # Mid explicite depuis FL/FR du 5.1 (FC est vide).
    mid = ROOT / "aurora_mid_24k.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(ROOT / "aurora_ref.m4a"),
            "-af", "pan=mono|c0=0.5*FL+0.5*FR,highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "24000", str(mid),
        ],
        check=True,
        capture_output=True,
    )

    x, sr = sf.read(mid)
    print("mid", x.shape, sr, "rms", float(np.sqrt(np.mean(x ** 2))))

    # HPSS : percussif/harmonique. La voix chantee/parlee tend vers l'harmonique.
    try:
        import librosa

        y = x.astype(np.float32)
        harm, perc = librosa.effects.hpss(y)
        sf.write(ROOT / "aurora_hpss_harm.wav", harm, sr)
        print("hpss harm rms", float(np.sqrt(np.mean(harm ** 2))), "perc", float(np.sqrt(np.mean(perc ** 2))))
    except Exception as e:
        print("hpss fail", e)

    from faster_whisper import WhisperModel

    modele = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    for label, path in [
        ("clean", ROOT / "aurora_clean_24k.wav"),
        ("mid", mid),
        ("prompt6s", ROOT / "aurora_prompt_6s.wav"),
    ]:
        segs, info = modele.transcribe(str(path), language=None, vad_filter=True)
        segs = list(segs)
        texte = " | ".join(f"{s.start:.1f}-{s.end:.1f} {s.text.strip()}" for s in segs)
        print(f"\n{label} lang={info.language} p={info.language_probability:.2f}")
        print(" ", texte or "(vide)")

    # Spectrogramme de la ref nettoyee vs eponine/estelle flat
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = [
        ("aurora_clean", ROOT / "aurora_clean_24k.wav"),
        ("eponine_flat", ROOT / "pocket_eponine_flat_fr.wav"),
        ("eponine_aurora", ROOT / "pocket_eponine_aurora_fr.wav"),
        ("estelle_flat", ROOT / "pocket_estelle_flat_fr.wav"),
        ("estelle_aurora", ROOT / "pocket_estelle_aurora_fr.wav"),
    ]
    fig, axes = plt.subplots(len(files), 1, figsize=(12, 2.1 * len(files)))
    for ax, (name, path) in zip(axes, files):
        y, s = sf.read(path)
        if y.ndim > 1:
            y = y.mean(axis=1)
        ax.specgram(y, NFFT=1024, Fs=s, noverlap=768, cmap="magma")
        ax.set_ylim(0, 8000)
        ax.set_title(name)
    fig.tight_layout()
    dest = ROOT / "_listen" / "spec_compare.png"
    dest.parent.mkdir(exist_ok=True)
    fig.savefig(dest, dpi=130)
    print("wrote", dest)


if __name__ == "__main__":
    main()
