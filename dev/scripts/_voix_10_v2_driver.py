"""Installe et lance les jobs TTS neufs un par un (paquet voix-10-samples-v2).

Ordre de production fixe (ORDRE 2026-09-14) : voxcpm2, neutts, audio8, dots_mf,
indextts25, firered3, raon, magpie. Anka (05) et Chatterbox MTL (10b) sont deja
livres : ils comptent comme acquis et ne sont jamais relances.

Un modele a la fois, aucun parallelisme GPU : chaque job tourne dans son propre
processus, ce qui libere modele et cache CUDA a sa sortie.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace")
VENV = Path("/workspace/models/tts-v2-venv")
PY = VENV / "bin" / "python"
PIP = VENV / "bin" / "pip"
HF = VENV / "bin" / "hf"
VENV_T28 = Path("/workspace/models/tts-v2-firered-venv")
PIP_T28 = VENV_T28 / "bin" / "pip"
MODELS = Path("/workspace/models/tts-v2")
SRC = Path("/workspace/models/tts-v2-src")
SCRIPT = ROOT / "dev" / "scripts" / "_voix_10_samples_v2.py"
LOGS = ROOT / "logs"

sys.path.insert(0, str(SCRIPT.parent))
sys.path.insert(0, str(ROOT))
from _voix_10_samples_v2 import SORTIE, SORTIES, ecrire_index, mp3_valide  # noqa: E402
from tts_burn_guard import refuser_colocation_live  # noqa: E402

SEQUENCE = ["voxcpm2", "neutts", "audio8", "dots_mf", "indextts25", "firered3", "raon", "magpie"]
LOG_NOM = {
    "voxcpm2": "01-voxcpm2", "neutts": "02-neutts", "audio8": "03-audio8",
    "dots_mf": "04-dots", "indextts25": "06-indextts25", "firered3": "07-firered3",
    "raon": "08-raon", "magpie": "09-magpie",
}


def env(extra_path: str = "") -> dict[str, str]:
    return {
        **os.environ,
        "HF_HOME": "/workspace/models/hf-cache",
        "PYTHONPATH": "/workspace" + (f":{extra_path}" if extra_path else ""),
        "PYTHONUNBUFFERED": "1",
    }


def sh(cmd: str) -> None:
    """Etape d'installation : leve si le code retour n'est pas 0."""
    print("+", cmd, flush=True)
    rc = subprocess.call(["bash", "-lc", f"set -euo pipefail; {cmd}"], env=env())
    if rc != 0:
        raise RuntimeError(f"rc={rc} : {cmd}")


def clone(url: str, nom: str, branche: str = "") -> Path:
    d = SRC / nom
    opt = f"--branch {branche} " if branche else ""
    sh(f'mkdir -p {SRC}; test -d "{d}/.git" || git clone --depth 1 {opt}{url} "{d}"')
    return d


def install_voxcpm2() -> None:
    sh(f"{PIP} install -U pip huggingface_hub soundfile numpy voxcpm")


def install_neutts() -> None:
    sh(f"{PIP} install -U neutts neucodec phonemizer")


def install_audio8() -> None:
    d = clone("https://github.com/Edge0-AI/Audio8_TTS.git", "Audio8_TTS")
    sh(f"{PIP} install -r {d}/requirements.txt")
    sh(f"{HF} download Edge0/Audio8-TTS-Preview-0.6b --local-dir {MODELS}/Audio8-TTS-Preview-0.6b")


def install_dots_mf() -> None:
    # dots.tts exige torch>=2.8 : venv isole partage avec FireRedTTS3 et Raon,
    # pour ne pas faire monter torch sous VoxCPM2 / Audio8 / Magpie (torch 2.6).
    sh(f"{PIP_T28} install dots.tts torch==2.8.0 torchaudio==2.8.0 transformers==5.6.2")


def install_indextts25() -> None:
    d = clone("https://github.com/index-tts/index-tts.git", "index-tts", "v2.5.0")
    sh(f"cd {d} && {PIP} install -U uv && {VENV}/bin/uv sync --extra webui")
    sh(f"{HF} download IndexTeam/IndexTTS-2.5 --local-dir {MODELS}/IndexTTS-2.5")


def install_firered3() -> None:
    d = clone("https://github.com/FireRedTeam/FireRedTTS3.git", "FireRedTTS3")
    # Pas de setup.py/pyproject dans le depot : requirements (sans flash_attn, build trop long)
    # dans le venv torch 2.8, le code est pris via PYTHONPATH.
    sh(f"test -x {VENV_T28}/bin/python || python3 -m venv {VENV_T28}")
    sh(f"grep -v '^flash_attn' {d}/requirements.txt > /tmp/firered-req.txt && {PIP_T28} install -r /tmp/firered-req.txt soundfile numpy scipy soxr")
    sh(f"{HF} download FireRedTeam/FireRedTTS3 --local-dir {MODELS}/FireRedTTS3 --exclude 'fireredtts3_instruct/*'")


def install_raon() -> None:
    d = clone("https://github.com/krafton-ai/Raon-OpenTTS.git", "Raon-OpenTTS")
    # Chaque commande est verifiee separement : un echec pip n'est plus masque.
    # `pip install -e` echoue : le pyproject declare un backend inexistant
    # (setuptools.backends._legacy). Dependances d'execution installees a la main,
    # code charge par PYTHONPATH (src/).
    sh(f"{PIP_T28} install torch==2.8.0 torchaudio==2.8.0 transformers==5.6.2 accelerate hydra-core "
       f"omegaconf datasets ema-pytorch tqdm soundfile numpy jieba pypinyin einops x-transformers "
       f"safetensors pydub")
    sh(f"{HF} download KRAFTON/Raon-OpenTTS-1B --local-dir {MODELS}/Raon-OpenTTS-1B")
    sh(f"{HF} download speechbrain/tts-hifigan-libritts-16kHz generator.ckpt --local-dir {MODELS}/Raon-vocoder")


def install_magpie() -> None:
    sh(f'{PIP} install -U "nemo_toolkit[tts]" kaldialign')


INSTALL = {
    "voxcpm2": install_voxcpm2, "neutts": install_neutts, "audio8": install_audio8,
    "dots_mf": install_dots_mf, "indextts25": install_indextts25,
    "firered3": install_firered3, "raon": install_raon, "magpie": install_magpie,
}
INTERPRETE = {
    "indextts25": SRC / "index-tts" / ".venv" / "bin" / "python",
    "dots_mf": VENV_T28 / "bin" / "python",
    "firered3": VENV_T28 / "bin" / "python",
    "raon": VENV_T28 / "bin" / "python",
}
PYTHONPATH_EXTRA = {
    "audio8": str(SRC / "Audio8_TTS"), "indextts25": str(SRC / "index-tts"),
    "firered3": str(SRC / "FireRedTTS3"), "raon": str(SRC / "Raon-OpenTTS" / "src"),
}


def job(name: str) -> int:
    py = INTERPRETE.get(name, PY)
    log = LOGS / f"tts-v2-{LOG_NOM[name]}.log"
    cmd = f'{py} {SCRIPT} --job {name} 2>&1 | tee -a "{log}"'
    print("+", cmd, flush=True)
    return subprocess.call(
        ["bash", "-lc", f"set -o pipefail; {cmd}"], env=env(PYTHONPATH_EXTRA.get(name, ""))
    )


def acquis() -> set[str]:
    return {job for job, fichier in SORTIES.items() if mp3_valide(SORTIE / fichier)}


def main() -> None:
    refuser_colocation_live()
    faits = acquis()
    print(f"acquis sur disque ({len(faits)}) : {sorted(faits)}", flush=True)
    fails: list[str] = []
    for name in SEQUENCE:
        if name in faits:
            print(f"== {name} : MP3 deja valide, saute", flush=True)
            continue
        print(f"\n======== INSTALL+RUN {name} ========", flush=True)
        try:
            INSTALL[name]()
        except RuntimeError as e:
            print(f"INSTALL FAIL {name}: {e}", flush=True)
            fails.append(name)
            continue
        rc = job(name)
        if rc == 0 and mp3_valide(SORTIE / SORTIES[name]):
            faits.add(name)
            print(f"JOB OK {name}  total={len(faits)}/10", flush=True)
        else:
            fails.append(name)
            print(f"JOB FAIL {name} rc={rc}", flush=True)

    ecrire_index()
    print(f"DONE {len(faits)}/10 fails={fails}", flush=True)
    if len(faits) < 10:
        sys.exit(2)


if __name__ == "__main__":
    main()
