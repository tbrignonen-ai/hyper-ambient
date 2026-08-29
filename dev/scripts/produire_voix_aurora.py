"""Produire les WAV de demonstration pour le timbre Aurora.

CPU only: le GPU porte deja llama-server + host-agent. Une phrase n'a pas
besoin du CUDA.
"""
from __future__ import annotations

import subprocess
import sys
import time
import traceback
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, "/workspace")

from src.mouth.voice_design import AURORA, FLAT, VoiceTreatment

VOIX = Path("/workspace/data/voix")
PHRASE = "Bonjour, je suis là. Prends ton temps, je t'écoute."
REF_M4A = VOIX / "aurora_ref.m4a"
CLEAN = VOIX / "aurora_clean_24k.wav"
PROMPT = VOIX / "aurora_prompt_6s.wav"


def ecrire(chemin: Path, x: np.ndarray, taux: int) -> None:
    pcm = np.clip(np.asarray(x), -32768, 32767).astype("<i2")
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(pcm.tobytes())


def lire_wav(chemin: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(chemin), "rb") as w:
        taux = w.getframerate()
        nch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x / 32768.0, taux


def nettoyer_reference() -> None:
    """Isoler la voix : 24 kHz mono, coupe rumble, denoise leger, loudnorm.

    Kyutai le dit dans le README Pocket : la qualite du sample est reproduite.
    Le m4a YouTube est un 5.1 dont seuls FL/FR portent du signal.
    """
    cmd = [
        "ffmpeg", "-y", "-i", str(REF_M4A),
        "-ac", "1", "-ar", "24000",
        "-af",
        "highpass=f=80,lowpass=f=12000,afftdn=nr=10:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
        str(CLEAN),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    x, taux = lire_wav(CLEAN)
    print(f"reference nettoyee : {len(x)/taux:.1f}s  {taux} Hz  rms={float(np.sqrt(np.mean(x*x))):.4f}")

    # 6 s les plus energiques, pour un prompt de clonage (Qwen veut ~3 s).
    win = int(taux * 6)
    hop = int(taux * 0.25)
    meilleur, ou = -1.0, 0
    for i in range(0, max(1, len(x) - win), hop):
        e = float(np.mean(x[i : i + win] ** 2))
        if e > meilleur:
            meilleur, ou = e, i
    ecrire(PROMPT, x[ou : ou + win] * 32768.0, taux)
    print(f"prompt 6s a t={ou/taux:.1f}s -> {PROMPT.name}")


def transcrire(chemin: Path) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster_whisper absent, pas de transcript")
        return ""
    t0 = time.perf_counter()
    modele = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    segments, info = modele.transcribe(str(chemin), language="fr")
    texte = " ".join(s.text.strip() for s in segments).strip()
    print(f"whisper {info.language} p={info.language_probability:.2f}  {time.perf_counter()-t0:.1f}s")
    print("transcript:", texte)
    return texte


EMB = Path("/workspace/models/pocket-tts/languages/french_24l/embeddings")


def _pcm16(audio) -> np.ndarray:
    x = audio.detach().cpu().float().numpy().ravel()
    return np.clip(x * 32767.0, -32768, 32767).astype(np.int16)


def _traiter(pcm: np.ndarray, profil, taux: int) -> np.ndarray:
    if profil is FLAT:
        return pcm
    return VoiceTreatment(profil, taux).process(pcm)


def pocket_tout() -> None:
    from pocket_tts import TTSModel

    print("chargement Pocket french_24l CPU…")
    t0 = time.perf_counter()
    modele = TTSModel.load_model(language="french_24l", temp=0.7)
    print(
        f"charge en {time.perf_counter()-t0:.1f}s  "
        f"has_voice_cloning={getattr(modele, 'has_voice_cloning', '?')}  "
        f"sr={modele.sample_rate}"
    )

    for nom in ("estelle", "eponine"):
        etat = modele.get_state_for_audio_prompt(str(EMB / f"{nom}.safetensors"))
        t1 = time.perf_counter()
        audio = modele.generate_audio(etat, PHRASE)
        brut = _pcm16(audio)
        dt = (time.perf_counter() - t1) * 1000
        for profil, suffixe in ((FLAT, "flat"), (AURORA, "aurora")):
            pcm = _traiter(brut, profil, modele.sample_rate)
            sortie = VOIX / f"pocket_{nom}_{suffixe}_fr.wav"
            ecrire(sortie, pcm, modele.sample_rate)
            print(f"pocket {nom:10} {suffixe:7}  {dt:.0f}ms synth  -> {sortie.name}")

    print("tentative clonage Pocket…")
    try:
        etat = modele.get_state_for_audio_prompt(str(CLEAN), truncate=True)
        audio = modele.generate_audio(etat, PHRASE)
        pcm = _traiter(_pcm16(audio), AURORA, modele.sample_rate)
        sortie = VOIX / "pocket_clone_aurora_fr.wav"
        ecrire(sortie, pcm, modele.sample_rate)
        print(f"clone pocket ok -> {sortie.name}")
    except Exception as e:
        print(f"clone pocket ECHEC : {type(e).__name__}: {e}")


def llama_tts_cloner(sortie: Path) -> None:
    gguf = Path("/workspace/models/tts/Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf")
    mm = Path("/workspace/models/tts/mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf")
    if not gguf.exists():
        print("llama-tts : gguf absent")
        return
    cmd = [
        "llama-tts",
        "-m", str(gguf),
        "-mm", str(mm),
        "--tts-speaker-file", str(PROMPT),
        "--tts-lang", "fr",
        "-ngl", "0",
        "-p", PHRASE,
        "-o", str(sortie),
    ]
    print("llama-tts clone CPU…")
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    print(f"llama-tts exit={r.returncode}  {dt:.1f}s")
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "")[-1500:]
        print(err)
    elif sortie.exists():
        print(f"llama-tts ok -> {sortie.name} ({sortie.stat().st_size} octets)")


def main() -> None:
    VOIX.mkdir(parents=True, exist_ok=True)
    nettoyer_reference()
    transcrire(CLEAN)
    pocket_tout()
    llama_tts_cloner(VOIX / "qwen3tts_aurora_fr.wav")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
