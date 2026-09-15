"""10 samples MP3, script long, modeles TTS NEUFS (pas v1).

Tourne dans mother-core-dev, venv /workspace/models/tts-v2-venv.
Un job a la fois : python _voix_10_samples_v2.py --job voxcpm2
Index : python _voix_10_samples_v2.py --index
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

from tts_burn_guard import refuser_colocation_live

os.environ.setdefault("HF_HOME", "/workspace/models/hf-cache")
os.environ.pop("HF_HUB_OFFLINE", None)

SORTIE = Path("/workspace/data/out/voix-10-samples-v2")
SCRIPT = Path("/workspace/dev/scripts/_voix_10_script.txt")
REF_WAV = Path("/workspace/data/voix/aurora_prompt_6s.wav")
REF_TXT = Path("/workspace/data/out/voix-10-samples-v2/_aurora_prompt_6s.txt")
META = SORTIE / "meta.jsonl"
MODELS = Path("/workspace/models/tts-v2")

# Transcript Whisper (anglais) du clip YouTube Aura Ray — 6 s les plus energiques.
REF_TEXT_FALLBACK = (
    "You can afford to sit passively while 2026 unfolds around you. "
    "The Galactic Federation has issued what they're calling their most "
    "critical human infrastructure alert of this decade."
)


def lire_script() -> str:
    texte = SCRIPT.read_text(encoding="utf-8").strip()
    texte = texte.replace("''", "'")
    return re.sub(r"\s+", " ", texte)


def phrases(texte: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", texte)
    return [p.strip() for p in parts if p.strip()]


def fragments(texte: str, limite: int = 150) -> list[str]:
    """Phrases, redecoupees aux virgules/points-virgules si >= limite."""
    out: list[str] = []
    for ph in phrases(texte):
        if len(ph) < limite:
            out.append(ph)
            continue
        cur = ""
        for bout in re.split(r"(?<=[,;:])\s+", ph):
            if cur and len(cur) + 1 + len(bout) >= limite:
                out.append(cur)
                cur = bout
            else:
                cur = f"{cur} {bout}".strip()
        if cur:
            out.append(cur)
    return out


def ref_text() -> str:
    if REF_TXT.exists():
        t = REF_TXT.read_text(encoding="utf-8").strip()
        if t:
            return t
    return REF_TEXT_FALLBACK


def pcm16(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    pic = float(np.max(np.abs(x))) if x.size else 0.0
    if pic > 1.0:
        x = x / pic * 0.99
    elif pic == 0.0:
        return np.zeros(0, dtype=np.int16)
    return np.clip(np.round(x * 32767.0), -32768, 32767).astype(np.int16)


def aurora(pcm: np.ndarray, taux: int) -> np.ndarray:
    from src.mouth.voice_design import PROFILES, VoiceTreatment

    if pcm.size == 0:
        return pcm
    return VoiceTreatment(PROFILES["aurora"], int(taux)).process(
        np.asarray(pcm, dtype=np.int16)
    )


def ecrire_wav(chemin: Path, pcm: np.ndarray, taux: int) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(taux))
        w.writeframes(np.asarray(pcm, dtype=np.int16).tobytes())


def wav_vers_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav), "-ac", "1",
            "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3),
        ],
        check=True,
        capture_output=True,
    )


def duree_wav(chemin: Path) -> float:
    with wave.open(str(chemin), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def gpu_vide() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass


# Fichier OUT de chaque job : sert a l'upsert (un MP3 valide n'est jamais resynthetise).
SORTIES = {
    "voxcpm2": "01-voxcpm2-clone-aurora.mp3",
    "neutts": "02-neutts-nano-french-clone-aurora.mp3",
    "audio8": "03-audio8-tts-0.6b-clone-aurora.mp3",
    "dots_mf": "04-dots-tts-mf-clone-aurora.mp3",
    "anka": "05-anka-tts-clone-aurora.mp3",
    "indextts25": "06-indextts25-clone-aurora.mp3",
    "firered3": "07-fireredtts3-base-clone-aurora.mp3",
    "raon": "08-raon-opentts-1b-clone-aurora.mp3",
    "magpie": "09-magpie-v2607-aria-fr.mp3",
    "chatterbox_mtl": "10b-chatterbox-mtl-v3-clone-aurora.mp3",
}


def duree_mp3(chemin: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(chemin)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def mp3_valide(chemin: Path) -> bool:
    """Critere disque : > 100 Ko, decodable sans erreur, duree 20-90 s."""
    if not chemin.is_file() or chemin.stat().st_size <= 100_000:
        return False
    dec = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(chemin), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if dec.returncode != 0 or dec.stderr.strip():
        return False
    return 20.0 <= duree_mp3(chemin) <= 90.0


def lire_meta() -> dict[str, dict]:
    seen: dict[str, dict] = {}
    if META.exists():
        for line in META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen[r["fichier"]] = r
    return seen


def ecrire_meta(ligne: dict) -> None:
    """Upsert : une seule ligne par fichier, la plus recente gagne."""
    seen = lire_meta()
    seen[ligne["fichier"]] = ligne
    tmp = META.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n"
                for r in sorted(seen.values(), key=lambda r: r["fichier"])),
        encoding="utf-8",
    )
    tmp.replace(META)


def livrer(nom: str, pcm: np.ndarray, taux: int, meta: dict) -> dict:
    SORTIE.mkdir(parents=True, exist_ok=True)
    wav = SORTIE / f"{nom}.wav"
    mp3 = SORTIE / f"{nom}.mp3"
    pcm = aurora(np.asarray(pcm, dtype=np.int16), int(taux))
    ecrire_wav(wav, pcm, taux)
    wav_vers_mp3(wav, mp3)
    sec = duree_wav(wav)
    wav.unlink(missing_ok=True)
    ligne = {
        "fichier": mp3.name,
        "chemin": str(mp3),
        "duree_s": round(sec, 2),
        "sr": int(taux),
        "octets": mp3.stat().st_size,
        **meta,
    }
    ecrire_meta(ligne)
    print(
        f"OK {mp3.name}  {sec:.2f}s  {taux} Hz  {mp3.stat().st_size} o  "
        f"{meta.get('modele')} / {meta.get('voix')}",
        flush=True,
    )
    if sec < 20:
        print(f"WARN duree < 20s : {mp3.name}", flush=True)
    return ligne


def concat_phrases(synth_one, texte: str) -> tuple[np.ndarray, int]:
    parts: list[np.ndarray] = []
    taux = 24000
    for i, phrase in enumerate(phrases(texte), 1):
        t0 = time.perf_counter()
        pcm, sr = synth_one(phrase)
        print(f"  phrase {i}/{len(phrases(texte))} {time.perf_counter()-t0:.1f}s  {phrase[:48]}", flush=True)
        pcm = pcm16(pcm) if pcm.dtype != np.int16 else pcm
        if pcm.size:
            parts.append(pcm)
            taux = int(sr)
    if not parts:
        raise RuntimeError("silence")
    return np.concatenate(parts), taux


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def job_voxcpm2(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from voxcpm import VoxCPM

    print("voxcpm2 chargement…", flush=True)
    import torch

    device = "cuda" if _cuda() else "cpu"
    # Le conteneur est plafonne a 8 Go de RAM : construit en fp32 sur CPU, le
    # modele 2B depasse la limite (OOM kill). On le construit directement en
    # bf16 sur le device cible, puis VoxCPM charge ses poids par-dessus.
    dtype_defaut = torch.get_default_dtype()
    torch.set_default_dtype(torch.bfloat16)
    try:
        with torch.device(device):
            model = VoxCPM.from_pretrained(
                "openbmb/VoxCPM2",
                load_denoiser=False,
                device=device,
                optimize=False,  # pas de torch.compile pour un run unique
            )
    finally:
        torch.set_default_dtype(dtype_defaut)
    sr = int(getattr(getattr(model, "tts_model", None), "sample_rate", 0) or 48000)

    def one(phrase: str):
        torch.manual_seed(42)  # voxcpm 2.0.3 (PyPI) n'accepte pas seed=
        wav = model.generate(
            text=phrase,
            reference_wav_path=str(REF_WAV),
            prompt_wav_path=str(REF_WAV),
            prompt_text=ref_text(),
            cfg_value=2.0,
            inference_timesteps=10,
        )
        return wav, sr

    pcm, taux = concat_phrases(one, texte)
    del model
    gpu_vide()
    return (
        "01-voxcpm2-clone-aurora",
        pcm,
        taux,
        {
            "modele": "openbmb/VoxCPM2 2B",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-04-03 / maj 2026-08-18",
            "note": "30 langues dont FR ; clonage zero-shot Aura Ray",
        },
    )


def job_neutts(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from neutts import NeuTTS

    device = "cuda" if _cuda() else "cpu"
    print(f"neutts-nano-french chargement {device}…", flush=True)
    tts = NeuTTS(
        backbone_repo="neuphonic/neutts-nano-french",
        backbone_device=device,
        codec_repo="neuphonic/neucodec",
        codec_device=device,
        seed=42,
    )
    ref = ref_text()
    codes = tts.encode_reference(str(REF_WAV))

    def one(phrase: str):
        wav = tts.infer(phrase, codes, ref)
        return np.asarray(wav, dtype=np.float32), int(tts.sample_rate)

    pcm, taux = concat_phrases(one, texte)
    del tts
    gpu_vide()
    return (
        "02-neutts-nano-french-clone-aurora",
        pcm,
        taux,
        {
            "modele": "neuphonic/neutts-nano-french ~120M",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-02-06 / maj 2026-08-26",
            "note": "Nano FR on-device, clonage CPU",
        },
    )


def job_chatterbox_nano(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from chatterbox.tts import ChatterboxTTS

    device = "cuda" if _cuda() else "cpu"
    print(f"chatterbox-en chargement {device}…", flush=True)
    model = ChatterboxTTS.from_pretrained(device=device)

    def one(phrase: str):
        wav = model.generate(phrase, audio_prompt_path=str(REF_WAV), exaggeration=0.35, cfg_weight=0.4)
        arr = wav.squeeze().detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
        return arr, int(model.sr)

    pcm, taux = concat_phrases(one, texte)
    del model
    gpu_vide()
    return (
        "03-chatterbox-en-clone-aurora",
        pcm,
        taux,
        {
            "modele": "ResembleAI/chatterbox EN 500M (pip 0.1.6)",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "poids HF maj 2026-06-10 / pip 0.1.6",
            "note": "SoTA EN zero-shot ; texte FR clone Aura (accent possible)",
        },
    )


def job_omnivoice(texte: str) -> tuple[str, np.ndarray, int, dict]:
    import torch
    from omnivoice import OmniVoice

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    print(f"omnivoice chargement {device} {dtype}…", flush=True)
    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=dtype)
    sr = int(getattr(getattr(model, "config", None), "sampling_rate", 24000) or 24000)
    try:
        prompt = model.create_voice_clone_prompt(
            ref_audio=str(REF_WAV), ref_text=ref_text()
        )
    except TypeError:
        prompt = None

    def one(phrase: str):
        kw = {"text": phrase, "language": "fr"}
        if prompt is not None:
            kw["voice_clone_prompt"] = prompt
        else:
            kw["ref_audio"] = str(REF_WAV)
            kw["ref_text"] = ref_text()
        out = model.generate(**kw)
        if isinstance(out, list):
            wav = out[0]
        elif isinstance(out, tuple):
            wav = out[0]
            if len(out) > 1 and isinstance(out[1], (int, float)):
                return (
                    out[0].detach().cpu().numpy()
                    if hasattr(out[0], "detach")
                    else np.asarray(out[0]),
                    int(out[1]),
                )
        elif hasattr(out, "audio"):
            wav = out.audio
        else:
            wav = out
        arr = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
        return arr, sr

    pcm, taux = concat_phrases(one, texte)
    del model
    gpu_vide()
    return (
        "04-omnivoice-clone-aurora",
        pcm,
        taux,
        {
            "modele": "k2-fsa/OmniVoice 0.6B",
            "voix": "clone aurora_prompt_6s lang=fr",
            "profil": "aurora",
            "date": "created 2026-03-30 / maj 2026-07-03",
            "note": "600+ langues, clonage FR ; maj juste avant le cutoff ~07-13",
        },
    )


def job_anka(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from anka import AnkaTTS

    device = "cuda" if _cuda() else "cpu"
    print(f"anka-tts chargement {device}…", flush=True)
    tts = AnkaTTS.from_pretrained("anka-tts/v0.1", device=device)
    wav = tts.synthesize(
        texte,
        ref_audio=str(REF_WAV),
        ref_text=ref_text(),
        validate_reference=False,
        chunk_by_sentence=True,
        speed=0.9,
    )
    pcm = pcm16(np.asarray(wav))
    del tts
    gpu_vide()
    if pcm.size == 0:
        raise RuntimeError("anka silence")
    return (
        "05-anka-tts-clone-aurora",
        pcm,
        24000,
        {
            "modele": "krmkayabasi/Anka-TTS v0.1 336M F5",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-09-11",
            "note": "F5-TTS fine-tune TR, clonage zero-shot (cross-lingual FR)",
        },
    )


def job_audio8(texte: str) -> tuple[str, np.ndarray, int, dict]:
    import torch
    from transformers import AutoModel, AutoProcessor

    ckpt = MODELS / "Audio8-TTS-Preview-0.6b"
    device = torch.device("cuda" if _cuda() else "cpu")
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    print(f"audio8-tts-0.6b chargement {device} {dtype}…", flush=True)
    processor = AutoProcessor.from_pretrained(str(ckpt), trust_remote_code=True)
    model = AutoModel.from_pretrained(
        str(ckpt), trust_remote_code=True, dtype=dtype
    ).eval().to(device)
    sr = int(model.config.codec_sample_rate)
    torch.manual_seed(42)
    generator = torch.Generator(device=device).manual_seed(42)
    ref = ref_text()

    def synth(frag: str, max_new_tokens: int):
        inputs = processor(
            text=[frag],
            reference_audio=[str(REF_WAV)],
            reference_text=[ref],
            return_tensors="pt",
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.inference_mode():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.8,
                top_p=0.95,
                top_k=50,
                do_sample=True,
                generator=generator,
                return_dict_in_generate=True,
            )
            wavs, lens = model.decode_audio(out.codes)
        return bool(out.finished[0]), wavs[0, : int(lens[0])].float().cpu().numpy()

    parts: list[np.ndarray] = []
    frags = fragments(texte, 150)
    for i, frag in enumerate(frags, 1):
        t0 = time.perf_counter()
        fini, wav = synth(frag, 1024)
        if not fini:
            print(f"  NO_EOS fragment {i}, relance 2000 tokens", flush=True)
            fini, wav = synth(frag, 2000)
        print(f"  fragment {i}/{len(frags)} {time.perf_counter()-t0:.1f}s eos={fini}  {frag[:48]}", flush=True)
        parts.append(pcm16(wav))
    del model, processor
    gpu_vide()
    return (
        "03-audio8-tts-0.6b-clone-aurora",
        np.concatenate(parts),
        sr,
        {
            "modele": "Edge0/Audio8-TTS-Preview-0.6b (DualAR 0.6B)",
            "voix": "clone aurora_prompt_6s + transcript",
            "profil": "aurora",
            "date": "Trending HF 2026-08-03 / 0.6B preview ete 2026",
            "note": "11 langues dont FR ; fragments < 150 car. (consigne officielle)",
        },
    )


def job_dots_mf(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from dots_tts.runtime import DotsTtsRuntime

    print("dots.tts-mf chargement…", flush=True)
    import torch
    from huggingface_hub import snapshot_download

    from dots_tts.models.dots_tts.model import DotsTtsModel

    # 8 Go de RAM conteneur : construit en fp32 sur CPU, le coeur 2B + son
    # state_dict depassent la limite. Construction bf16 directement sur GPU,
    # puis vocodeur et encodeur de locuteur remis en fp32 et recharges depuis
    # leurs fichiers (pas de perte de precision sur ces deux modules).
    dtype_defaut = torch.get_default_dtype()
    torch.set_default_dtype(torch.bfloat16)
    try:
        with torch.device("cuda"):
            rt = DotsTtsRuntime.from_pretrained("dots-studio/dots.tts-mf", precision="bfloat16")
    finally:
        torch.set_default_dtype(dtype_defaut)
    snap = Path(snapshot_download("dots-studio/dots.tts-mf", local_files_only=True))
    for module, fichier in (
        (rt.model.vocoder, DotsTtsModel.VOCODER_FILENAME),
        (rt.model.xvector_extractor, DotsTtsModel.SPEAKER_ENCODER_FILENAME),
    ):
        module.float()
        DotsTtsModel._load_artifact_module(module, snap / fichier)

    from dots_tts.utils.util import seed_everything

    def one(phrase: str):
        seed_everything(42)
        result = rt.generate(
            text=phrase,
            prompt_audio_path=str(REF_WAV),
            prompt_text=ref_text(),
        )
        arr = result["audio"]
        arr = arr.detach().float().cpu().squeeze().numpy() if hasattr(arr, "detach") else np.asarray(arr)
        return arr, int(result["sample_rate"])

    pcm, taux = concat_phrases(one, texte)
    del rt
    gpu_vide()
    return (
        "04-dots-tts-mf-clone-aurora",
        pcm,
        taux,
        {
            "modele": "dots-studio/dots.tts-mf 2B MeanFlow",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-06-04 / maj 2026-08-11",
            "note": "24 langues dont FR ; MeanFlow distille, 4 steps",
        },
    )


def job_indextts25(texte: str) -> tuple[str, np.ndarray, int, dict]:
    ckpt = MODELS / "IndexTTS-2.5"
    from indextts.infer_v2_5 import IndexTTS2

    print("indextts-2.5 chargement…", flush=True)
    tts = IndexTTS2(
        cfg_path=str(ckpt / "config.yaml"),
        model_dir=str(ckpt),
        use_bf16=True,
        use_cuda_kernel=False,  # pas de compilation du noyau BigVGAN pour un run unique
    )
    lang = os.environ.get("INDEXTTS_LANG", "fr")
    tmp = SORTIE / "_idx_tmp.wav"
    parts: list[np.ndarray] = []
    taux = 24000
    for i, phrase in enumerate(phrases(texte), 1):
        t0 = time.perf_counter()
        tts.infer(
            spk_audio_prompt=str(REF_WAV),
            text=phrase,
            lang=lang,
            output_path=str(tmp),
            verbose=False,
        )
        print(f"  phrase {i} {time.perf_counter()-t0:.1f}s  {phrase[:48]}", flush=True)
        with wave.open(str(tmp), "rb") as w:
            taux = w.getframerate()
            n = w.getnframes()
            raw = w.readframes(n)
            pcm = np.frombuffer(raw, dtype=np.int16)
        if pcm.size:
            parts.append(pcm)
    tmp.unlink(missing_ok=True)
    del tts
    gpu_vide()
    if not parts:
        raise RuntimeError("indextts silence")
    return (
        "06-indextts25-clone-aurora",
        np.concatenate(parts),
        taux,
        {
            "modele": "IndexTeam/IndexTTS-2.5 0.8B",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-08-10",
            "note": f"lang={lang} (API sans auto) ; FR hors langues natives ZH/EN/JA/ES : cross-lingual",
        },
    )


def job_firered3(texte: str) -> tuple[str, np.ndarray, int, dict]:
    import torchaudio
    from fireredtts3.core import FireRedTTS3

    ckpt = MODELS / "FireRedTTS3"
    print("fireredtts3-base chargement…", flush=True)
    # Langue imposee ("French") : ni detection fasttext (telechargement), ni TN zh/en.
    tts = FireRedTTS3(str(ckpt), use_fasttext=False, use_wetext=False, use_llm_tn=False)
    prompt_audio, prompt_sr = torchaudio.load(str(REF_WAV))

    def one(phrase: str):
        gen_audio, gen_sr = tts.generate(
            language="French",
            prompt_text=ref_text(),
            prompt_audio=prompt_audio,
            prompt_audio_sr=prompt_sr,
            text=phrase,
            do_tn=False,
            seed=1234,
        )
        arr = (
            gen_audio.detach().float().cpu().numpy()
            if hasattr(gen_audio, "detach")
            else np.asarray(gen_audio)
        )
        return arr, int(gen_sr)

    pcm, taux = concat_phrases(one, texte)
    del tts
    gpu_vide()
    return (
        "07-fireredtts3-base-clone-aurora",
        pcm,
        taux,
        {
            "modele": "FireRedTeam/FireRedTTS3-Base 1.7B",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-08-13",
            "note": "24 langues dont FR ; clonage zero-shot",
        },
    )


def job_raon(texte: str) -> tuple[str, np.ndarray, int, dict]:
    import torch
    from ema_pytorch import EMA
    from omegaconf import OmegaConf
    from safetensors.torch import load_file

    from f5_tts.infer import utils_infer as ui
    from f5_tts.model import CFM, DiT
    from f5_tts.model.utils import get_tokenizer

    src = Path("/workspace/models/tts-v2-src/Raon-OpenTTS")
    ckpt_dir = MODELS / "Raon-OpenTTS-1B"
    cfg = OmegaConf.load(str(src / "src/f5_tts/configs/1b.yaml"))
    ckpt = next(iter(sorted(ckpt_dir.glob("*.safetensors"))), None) or next(
        iter(sorted(ckpt_dir.glob("*.pt"))), None
    )
    if ckpt is None:
        raise RuntimeError(f"aucun checkpoint dans {ckpt_dir}")
    vocab = ckpt_dir / "vocab.txt"
    if not vocab.exists():
        vocab = src / cfg.model.tokenizer_path
    vocab_char_map, vocab_size = get_tokenizer(str(vocab), "custom")
    device = torch.device("cuda" if _cuda() else "cpu")
    print(f"raon-opentts-1B chargement {ckpt.name} vocab={vocab_size}…", flush=True)
    mel = OmegaConf.to_container(cfg.model.mel_spec, resolve=True)
    model = CFM(
        transformer=DiT(
            **OmegaConf.to_container(cfg.model.arch, resolve=True),
            text_num_embeds=vocab_size,
            mel_dim=mel["n_mel_channels"],
        ),
        mel_spec_kwargs=mel,
        vocab_char_map=vocab_char_map,
    ).to(device)
    ema = EMA(model, include_online_model=False).to(device)
    if ckpt.suffix == ".safetensors":
        state = {"ema_model_state_dict": load_file(str(ckpt))}
    else:
        # 16,7 Go (etat d'entrainement complet) pour 8 Go de RAM conteneur :
        # mmap, seuls les tenseurs EMA sont effectivement lus.
        state = torch.load(str(ckpt), map_location="cpu", mmap=True, weights_only=False)
    ema.load_state_dict(state["ema_model_state_dict"])
    for key, param in ema.ema_model.state_dict().items():
        model.state_dict()[key].copy_(param)
    model.eval()
    del ema, state
    vocoder = ui.load_vocoder(
        vocoder_name=mel["mel_spec_type"],
        is_local=True,
        local_path=str(MODELS / "Raon-vocoder"),
        device=device,
    )
    # Vocabulaire caracteres anglais minuscules : on garde les accents,
    # les caracteres inconnus tombent sur l'index 0 du tokenizer.
    ref = ref_text().lower()

    def one(phrase: str):
        wav, sr, _ = ui.infer_process(
            str(REF_WAV), ref, phrase.lower(), model, vocoder,
            mel_spec_type=mel["mel_spec_type"], device=device,
        )
        return np.asarray(wav, dtype=np.float32), int(sr)

    pcm, taux = concat_phrases(one, texte)
    tts = model
    del vocoder, model
    del tts
    gpu_vide()
    return (
        "08-raon-opentts-1b-clone-aurora",
        pcm,
        taux,
        {
            "modele": "KRAFTON/Raon-OpenTTS-1B DiT (F5 arch, depot krafton-ai, config 1b + HiFi-GAN 16k)",
            "voix": "clone aurora_prompt_6s",
            "profil": "aurora",
            "date": "created 2026-05-21 / maj 2026-08-19",
            "note": "open-data 1B, clonage F5 (EN train, cross-lingual FR)",
        },
    )


def job_magpie(texte: str) -> tuple[str, np.ndarray, int, dict]:
    try:
        from nemo.collections.tts.models import MagpieTTS_Model as MagpieTTSModel
    except ImportError:
        from nemo.collections.tts.models import MagpieTTSModel

    print("magpie v2607 chargement…", flush=True)
    model = MagpieTTSModel.from_pretrained("nvidia/magpie_tts_multilingual_357m")
    model.eval()
    if _cuda():
        model = model.cuda()
    sr = int(getattr(model, "output_sample_rate", getattr(model, "sample_rate", 22050)))

    def one(phrase: str):
        import torch

        with torch.inference_mode():
            audio, audio_len = model.do_tts(
                # Pas de TN : le script n'a ni chiffre ni abreviation, et la TN tirerait
                # nemo_text_processing/pynini, fragiles dans ce conteneur.
                phrase, language="fr", apply_TN=False, use_cfg=True, speaker_index=0  # Aria
            )
        n = int(audio_len[0].item() if hasattr(audio_len[0], "item") else audio_len[0])
        arr = audio[0, :n].float().cpu().numpy()
        return arr, sr

    pcm, taux = concat_phrases(one, texte)
    del model
    gpu_vide()
    return (
        "09-magpie-v2607-aria-fr",
        pcm,
        taux,
        {
            "modele": "nvidia/magpie_tts_multilingual_357m v2607 364M",
            "voix": "Aria (idx 0) FR",
            "profil": "aurora",
            "date": "v2607 2026-07-21 / maj 2026-09-09",
            "note": "FR natif, locutrice Aria, 364M, GGUF aussi dispo",
        },
    )


def job_breeze(texte: str) -> tuple[str, np.ndarray, int, dict]:
    # Repli : Breeze TTS 2 (EN/ZH, 2026-08-25). Texte FR quand meme.
    raise RuntimeError("breeze: installer d abord le runtime BreezeBlue/Breeze-TTS-2")


def job_chatterbox_mtl(texte: str) -> tuple[str, np.ndarray, int, dict]:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "cuda" if _cuda() else "cpu"
    print(f"chatterbox-mtl chargement {device}…", flush=True)
    try:
        model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
        tag = "V3"
    except TypeError:
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        tag = "MTL"

    def one(phrase: str):
        wav = model.generate(phrase, language_id="fr", audio_prompt_path=str(REF_WAV))
        arr = wav.squeeze().detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
        return arr, int(model.sr)

    pcm, taux = concat_phrases(one, texte)
    del model
    gpu_vide()
    return (
        "10b-chatterbox-mtl-v3-clone-aurora",
        pcm,
        taux,
        {
            "modele": "ResembleAI/chatterbox multilingual V3 500M",
            "voix": "clone aurora_prompt_6s language_id=fr",
            "profil": "aurora",
            "date": "V3 2026-06-10 (hors cutoff strict, repli FR)",
            "note": "REPLI seulement si un job <2 mois echoue",
        },
    )


JOBS = {
    "voxcpm2": job_voxcpm2,
    "neutts": job_neutts,
    "audio8": job_audio8,
    "chatterbox_nano": job_chatterbox_nano,
    "omnivoice": job_omnivoice,
    "anka": job_anka,
    "dots_mf": job_dots_mf,
    "indextts25": job_indextts25,
    "firered3": job_firered3,
    "raon": job_raon,
    "magpie": job_magpie,
    "chatterbox_mtl": job_chatterbox_mtl,
    "breeze": job_breeze,
}


def _cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


# Revision HF (sha) et licence relevees le 2026-09-14 via l'API Hugging Face.
FICHES = {
    "01-voxcpm2-clone-aurora.mp3": ("openbmb/VoxCPM2@32279ef", "Apache-2.0"),
    "02-neutts-nano-french-clone-aurora.mp3": ("neuphonic/neutts-nano-french@c04ee51 (gated)", "other (Neuphonic)"),
    "03-audio8-tts-0.6b-clone-aurora.mp3": ("Edge0/Audio8-TTS-Preview-0.6b@f07040f", "Apache-2.0"),
    "04-dots-tts-mf-clone-aurora.mp3": ("dots-studio/dots.tts-mf@c28105a", "Apache-2.0"),
    "05-anka-tts-clone-aurora.mp3": ("krmkayabasi/Anka-TTS@f1ce92d", "CC-BY-NC-4.0"),
    "06-indextts25-clone-aurora.mp3": ("IndexTeam/IndexTTS-2.5@c39ce5b", "other (bilibili IndexTTS)"),
    "07-fireredtts3-base-clone-aurora.mp3": ("FireRedTeam/FireRedTTS3@dcf1bdc", "Apache-2.0"),
    "08-raon-opentts-1b-clone-aurora.mp3": ("KRAFTON/Raon-OpenTTS-1B@42dcf59", "CC-BY-NC-4.0"),
    "09-magpie-v2607-aria-fr.mp3": ("nvidia/magpie_tts_multilingual_357m@1980687 (v2607)", "NVIDIA Open Model License"),
    "10b-chatterbox-mtl-v3-clone-aurora.mp3": ("ResembleAI/chatterbox@5bb1f6e", "MIT"),
}
VALIDATION = Path("/workspace/logs/tts-v2/validation.json")


def ecrire_index() -> None:
    lignes = list(lire_meta().values())
    lignes.sort(key=lambda r: r["fichier"])
    val = json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.exists() else {}
    corps = [
        "# INDEX — 10 samples voix FR v2 (modeles TTS neufs)",
        "",
        "Script : `nights/2026-09-13-SCRIPT-VOIX-LONG.txt` (copie `dev/scripts/_voix_10_script.txt`).",
        "Cible esthetique : Aura Ray — douce, presentielle, proche. Profil DSP `aurora` applique une fois.",
        "Ref clone : `data/voix/aurora_prompt_6s.wav` (anglais, clonage cross-lingual) + `_aurora_prompt_6s.txt`.",
        "Interdits : Pocket, Piper, Supertonic, Qwen3-TTS, mms-tts-fra.",
        "Slot 10b Chatterbox MTL V3 = REPLI hors cutoff (poids 2026-06-10).",
        "",
        "Controle auto = faster-whisper large-v3-turbo : langue detectee, recouvrement de mots avec le script,",
        "derniers mots entendus, fuite du prompt anglais. Ce n'est pas une ecoute humaine.",
        "",
        "| Slot | Fichier | Modele (revision) | Licence | Duree | SR | Taille | Synth | VRAM max | Langue | Recouv. | Fin | Auto OK |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|---:|---|---|",
    ]
    for r in lignes:
        v = val.get(r["fichier"], {})
        rev, lic = FICHES.get(r["fichier"], (r.get("modele", ""), "?"))
        vram = f"{r['vram_max_mib']} Mio" if r.get("vram_max_mib") else "—"
        corps.append(
            f"| {r['fichier'][:3].rstrip('-')} | `{r['fichier']}` | {rev} | {lic} | "
            f"{r.get('duree_s', 0):.1f} s | {r.get('sr', '')} | {r.get('octets', 0) // 1024} Ko | "
            f"{r.get('synth_s', '—')} s | {vram} | {v.get('langue_detectee', '—')} | "
            f"{v.get('recouvrement_mots', '—')} | {v.get('fin_audible', '—')} | "
            f"{'oui' if v.get('bloquant_ok') else ('NON' if v else '—')} |"
        )
    mp3s = sorted(SORTIE.glob("*.mp3"))
    manquants = [f for f in FICHES if not (SORTIE / f).exists()]
    corps += [
        "",
        f"MP3 sur disque : **{len(mp3s)} / 10**",
    ]
    if manquants:
        corps.append("Manquants : " + ", ".join(f"`{m}`" for m in manquants))
    corps.append("")
    index = SORTIE / "INDEX.md"
    index.write_text("\n".join(corps) + "\n", encoding="utf-8")
    print(f"INDEX {index} n_meta={len(lignes)} n_mp3={len(mp3s)}", flush=True)


def transcrire_ref() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    if REF_TXT.exists() and REF_TXT.stat().st_size > 10:
        print(f"ref_text deja la : {REF_TXT.read_text(encoding='utf-8')[:80]}", flush=True)
        return
    from faster_whisper import WhisperModel

    cache = Path("/workspace/models/hf-cache/hub/models--Systran--faster-whisper-base")
    snaps = list(cache.glob("snapshots/*"))
    model_path = str(snaps[0]) if snaps else "base"
    print(f"whisper transcribe {REF_WAV} via {model_path}", flush=True)
    m = WhisperModel(model_path, device="cpu", compute_type="int8")
    segs, info = m.transcribe(str(REF_WAV), language="en")
    txt = " ".join(s.text.strip() for s in segs).strip()
    if not txt:
        txt = REF_TEXT_FALLBACK
    REF_TXT.write_text(txt + "\n", encoding="utf-8")
    print(f"ref_text ({info.language}): {txt}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--job", default="")
    p.add_argument("--index", action="store_true")
    p.add_argument("--transcribe", action="store_true")
    args = p.parse_args()
    sys.path.insert(0, "/workspace")
    if args.transcribe:
        transcrire_ref()
        return
    if args.index:
        ecrire_index()
        return
    refuser_colocation_live()
    if not args.job:
        raise SystemExit("usage: --job NAME | --index | --transcribe")
    if args.job not in JOBS:
        raise SystemExit(f"jobs: {sorted(JOBS)}")
    if not REF_WAV.exists():
        raise SystemExit(f"manque {REF_WAV}")
    cible = SORTIE / SORTIES.get(args.job, "_")
    if args.job in SORTIES and mp3_valide(cible):
        print(f"SKIP {cible.name} deja valide ({duree_mp3(cible):.1f}s)", flush=True)
        return
    texte = lire_script()
    print(f"job={args.job} script={len(texte)} car {len(phrases(texte))} phrases", flush=True)
    t0 = time.perf_counter()
    nom, pcm, taux, meta = JOBS[args.job](texte)
    if args.job in SORTIES and f"{nom}.mp3" != SORTIES[args.job]:
        raise SystemExit(f"nom OUT incoherent : {nom} vs {SORTIES[args.job]}")
    meta["synth_s"] = round(time.perf_counter() - t0, 1)
    if _cuda():
        import torch

        meta["vram_max_mib"] = round(torch.cuda.max_memory_allocated() / 2**20)
    livrer(nom, pcm, taux, meta)
    gpu_vide()


if __name__ == "__main__":
    main()
