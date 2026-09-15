"""Recette World — 1 image / 1 clip, sans jamais charger LingBot.

WorldPort (port.py) est le contrat start/step/stop. Ce module repond a la
decouverte : qui genere, comment, a quelle cadence, ou ca s'affiche, et
quelle commande amont lance un clip. Le backend par defaut reste un bouchon
RGB 832x480. Le run LingBot n'est declare possible que si VRAM, torch,
flash-attn et les poids sont tous la — ce qui n'est pas le cas ici.

Licence des poids vises : CC-BY-NC-SA 4.0.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any, Mapping, Optional

from src.world.port import (
    HAUTEUR,
    LARGEUR,
    LICENCE,
    MODELE_ID,
    PAS_PAR_CHUNK,
    VRAM_ESTIMEE_MB,
    FrameChunk,
    VramInsuffisante,
    WorldPort,
    lire_vram_libre_mb,
    vers_evenement,
)

TASK = "i2v-1.3B"
PIPELINE = "WanI2VCausal"
SIZE_OFFICIEL = "480*832"
CHUNK_SIZE = 4
FRAME_NUM_CLIP = 361
FRAME_NUM_UN_IMAGE = 5
SAMPLE_FPS_SCRIPT = 16
FPS_CLAIM_DEPLOY = 60
RESOLUTION_CLAIM_DEPLOY = "720p"
NPROC_README = 4
NPROC_RUN_FAST_SH = 2
NPROC_MONO = 1
T5_CHECKPOINT = "models_t5_umt5-xxl-enc-bf16.pth"
VAE_CHECKPOINT = "Wan2.1_VAE.pth"
T5_TOKENIZER = "google/umt5-xxl"
PROMPT_LAC = (
    "A serene lakeside scene with a lone tree standing in calm water, "
    "surrounded by distant snow-capped mountains under a bright blue sky "
    "with drifting white clouds — gentle ripples reflect the tree and sky, "
    "creating a tranquil, meditative atmosphere."
)
IMAGE_AMORCE = "examples/03/image.jpg"
ACTION_PATH = "examples/03"
CKPT_DIR = "lingbot-world-v2-1.3b-causal-fast"
ASSETS_DIR = "lingbot-world-v2-14b-causal-fast"
DL_DIT_OCTETS = 6841581806
DIT_PARAMS_F32 = 1709502016
OCTETS_RGB = LARGEUR * HAUTEUR * 3


def commande_1_clip() -> list[str]:
    """Commande README 1.3B : clip 361 frames, 4 GPU, FSDP, assets 14B."""
    return [
        "torchrun",
        f"--nproc_per_node={NPROC_README}",
        "generate.py",
        "--task",
        TASK,
        "--size",
        SIZE_OFFICIEL,
        "--ckpt_dir",
        CKPT_DIR,
        "--assets_dir",
        ASSETS_DIR,
        "--image",
        IMAGE_AMORCE,
        "--action_path",
        ACTION_PATH,
        "--dit_fsdp",
        "--t5_fsdp",
        "--ulysses_size",
        str(NPROC_README),
        "--frame_num",
        str(FRAME_NUM_CLIP),
        "--local_attn_size",
        "18",
        "--sink_size",
        "6",
        "--prompt",
        PROMPT_LAC,
    ]


def commande_1_image() -> list[str]:
    """Plus petit clip 4n+1 en mono-GPU : generate.py refuse FSDP hors dist."""
    return [
        "python",
        "generate.py",
        "--task",
        TASK,
        "--size",
        SIZE_OFFICIEL,
        "--ckpt_dir",
        CKPT_DIR,
        "--assets_dir",
        ASSETS_DIR,
        "--image",
        IMAGE_AMORCE,
        "--action_path",
        ACTION_PATH,
        "--t5_cpu",
        "--offload_model",
        "true",
        "--ulysses_size",
        str(NPROC_MONO),
        "--frame_num",
        str(FRAME_NUM_UN_IMAGE),
        "--chunk_size",
        str(CHUNK_SIZE),
        "--local_attn_size",
        "18",
        "--sink_size",
        "6",
        "--prompt",
        PROMPT_LAC,
    ]


def diagnostiquer(
    *,
    vram_libre_mb: Optional[float] = None,
    executeur_vram: Optional[Any] = None,
    modules: Optional[Mapping[str, bool]] = None,
    racine_poids: Optional[Path] = None,
) -> dict[str, Any]:
    """Etat machine pour un run. N'importe jamais torch : on lui passe le verdict."""
    if vram_libre_mb is None:
        vram_libre_mb = lire_vram_libre_mb(executeur=executeur_vram)

    vram_ok = vram_libre_mb is not None and float(vram_libre_mb) >= VRAM_ESTIMEE_MB
    mods = dict(modules or {})
    torch_ok = bool(mods.get("torch", False))
    flash_ok = bool(mods.get("flash_attn", False))

    racine = Path(racine_poids) if racine_poids is not None else None
    poids_dit = _existe(racine, "model-00001-of-00006.safetensors")
    poids_t5 = _existe(racine, T5_CHECKPOINT)
    poids_vae = _existe(racine, VAE_CHECKPOINT)
    run_lingbot = bool(
        vram_ok and torch_ok and flash_ok and poids_dit and poids_t5 and poids_vae
    )
    return {
        "vram_libre_mb": vram_libre_mb,
        "seuil_vram_mb": VRAM_ESTIMEE_MB,
        "vram_ok": vram_ok,
        "torch": torch_ok,
        "flash_attn": flash_ok,
        "poids_dit": poids_dit,
        "poids_t5": poids_t5,
        "poids_vae": poids_vae,
        "run_lingbot": run_lingbot,
        "run_bouchon": vram_ok,
        "licence": LICENCE,
        "modele": MODELE_ID,
        "pipeline": PIPELINE,
        "fps_script": SAMPLE_FPS_SCRIPT,
        "fps_claim_deploy": FPS_CLAIM_DEPLOY,
    }


class BouchonRgb:
    """Quatre trames RGB 832x480, muettes. Pas un modele."""

    def step(self, action: Mapping[str, Any]) -> FrameChunk:
        del action
        trame = pixels_bouchon()
        return FrameChunk(frames=tuple(trame for _ in range(PAS_PAR_CHUNK)))


def pixels_bouchon() -> bytes:
    """Degrade teal : ouvrir le fichier ne peut pas passer pour du LingBot."""
    lignes: list[bytes] = []
    for y in range(HAUTEUR):
        teinte = 24 + (y * 40) // HAUTEUR
        pixel = bytes((teinte, teinte + 16, teinte + 24))
        lignes.append(pixel * LARGEUR)
    return b"".join(lignes)


def produire_image(chemin: Path, *, rgb: Optional[bytes] = None) -> Path:
    """Ecrit un PNG 832x480. Defaut = bouchon teal, jamais un tenseur modele."""
    brut = rgb if rgb is not None else pixels_bouchon()
    if len(brut) != OCTETS_RGB:
        raise ValueError(f"RGB attendu {OCTETS_RGB} octets, recu {len(brut)}")
    cible = Path(chemin)
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(_encoder_png(LARGEUR, HAUTEUR, brut))
    return cible


def tenter_run(
    *,
    vram_libre_mb: Optional[float] = None,
    dossier: Path,
    executeur_vram: Optional[Any] = None,
    modules: Optional[Mapping[str, bool]] = None,
    racine_poids: Optional[Path] = None,
) -> dict[str, Any]:
    """Un pas WorldPort + 1 PNG. LingBot n'est jamais charge."""
    etat = diagnostiquer(
        vram_libre_mb=vram_libre_mb,
        executeur_vram=executeur_vram,
        modules=modules,
        racine_poids=racine_poids,
    )
    if not etat["run_bouchon"]:
        libre = etat["vram_libre_mb"]
        raise VramInsuffisante(
            f"VRAM libre {libre} Mio < seuil {VRAM_ESTIMEE_MB:.0f} Mio"
        )
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    port = WorldPort(
        vram_libre_mb=float(etat["vram_libre_mb"]),
        backend=BouchonRgb(),
        processus_separe=False,
    )
    port.start("un lac calme sous un ciel bleu")
    chunk = port.step({"text_event": "la brume se leve"})
    image = produire_image(dossier / "world-1-image.png", rgb=chunk.frames[0])
    evenement = vers_evenement(chunk)
    port.stop()
    return {
        "mode": "bouchon",
        "lingbot": False,
        "image": str(image),
        "chunk_pas": chunk.pas,
        "largeur": chunk.width,
        "hauteur": chunk.height,
        "evenement": evenement,
        "diag": etat,
    }


def _existe(racine: Optional[Path], nom: str) -> bool:
    if racine is None:
        return False
    if (racine / nom).is_file():
        return True
    return any(racine.rglob(nom))


def _encoder_png(largeur: int, hauteur: int, rgb: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    rangees = []
    pas = largeur * 3
    for y in range(hauteur):
        rangees.append(b"\x00" + rgb[y * pas : (y + 1) * pas])
    ihdr = struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rangees), 9))
        + chunk(b"IEND", b"")
    )
