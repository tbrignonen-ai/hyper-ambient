"""Recette World : 1 image / 1 clip, sans charger LingBot.

Ce module complete WorldPort (Cursor B) : il fige qui genere, comment,
a quelle cadence, ou ca s'affiche, licence / VRAM / telechargement, et
la commande amont pour un clip. Aucun test ici n'importe torch, ni
flash-attn, ni le host-agent, ni qwen3_asr.

Preuve attendue : un PNG 832x480 ecrit par le bouchon RGB, et un
diagnostic qui refuse le run LingBot tant que poids + torch manquent.
"""
from __future__ import annotations

import ast
import struct
from pathlib import Path

import pytest

from src.world.port import (
    HAUTEUR,
    LARGEUR,
    LICENCE,
    PAS_PAR_CHUNK,
    VRAM_ESTIMEE_MB,
    VramInsuffisante,
    vers_evenement,
)
from src.world.recette import (
    CHUNK_SIZE,
    DL_DIT_OCTETS,
    FPS_CLAIM_DEPLOY,
    FRAME_NUM_CLIP,
    FRAME_NUM_UN_IMAGE,
    NPROC_README,
    NPROC_RUN_FAST_SH,
    SAMPLE_FPS_SCRIPT,
    SIZE_OFFICIEL,
    TASK,
    T5_CHECKPOINT,
    VAE_CHECKPOINT,
    BouchonRgb,
    commande_1_clip,
    commande_1_image,
    diagnostiquer,
    produire_image,
    tenter_run,
)


ROOT = Path(__file__).resolve().parents[2]
RECETTE_PY = ROOT / "src" / "world" / "recette.py"


def _png_taille(chemin: Path) -> tuple[int, int]:
    brut = chemin.read_bytes()
    assert brut[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", brut[16:24])


# --- identite amont --------------------------------------------------------


def test_tache_officielle_est_i2v_1_3b():
    assert TASK == "i2v-1.3B"


def test_taille_officielle_est_480_par_832():
    assert SIZE_OFFICIEL == "480*832"
    assert (LARGEUR, HAUTEUR) == (832, 480)


def test_frame_num_clip_est_4n_plus_1():
    assert FRAME_NUM_CLIP == 361
    assert (FRAME_NUM_CLIP - 1) % 4 == 0


def test_frame_num_une_image_est_4n_plus_1():
    assert FRAME_NUM_UN_IMAGE == 5
    assert (FRAME_NUM_UN_IMAGE - 1) % 4 == 0


def test_chunk_public_est_4_pas():
    assert CHUNK_SIZE == 4
    assert CHUNK_SIZE == PAS_PAR_CHUNK


def test_fps_script_public_est_16_claim_deploy_60():
    assert SAMPLE_FPS_SCRIPT == 16
    assert FPS_CLAIM_DEPLOY == 60


def test_nproc_readme_4_et_run_fast_sh_2():
    assert NPROC_README == 4
    assert NPROC_RUN_FAST_SH == 2


def test_assets_t5_et_vae_sont_ceux_du_14b():
    assert T5_CHECKPOINT == "models_t5_umt5-xxl-enc-bf16.pth"
    assert VAE_CHECKPOINT == "Wan2.1_VAE.pth"


def test_licence_reste_nc():
    assert LICENCE == "CC-BY-NC-SA-4.0"


def test_dit_pese_environ_6_8_go_sur_hf():
    assert DL_DIT_OCTETS == 6841581806


# --- commandes : clip README vs 1 image mono-GPU ---------------------------


def test_commande_1_clip_suit_le_readme_4_gpu():
    argv = commande_1_clip()
    joint = " ".join(argv)
    assert argv[0] == "torchrun"
    assert "--nproc_per_node=4" in argv
    assert "--task" in argv and "i2v-1.3B" in argv
    assert "--size" in argv and "480*832" in argv
    assert "--frame_num" in argv and "361" in argv
    assert "--assets_dir" in argv
    assert "--dit_fsdp" in argv
    assert "--t5_fsdp" in argv
    assert "--ulysses_size" in argv and "4" in argv
    assert "generate.py" in joint


def test_commande_1_image_est_mono_gpu_sans_fsdp():
    argv = commande_1_image()
    assert argv[0] == "python"
    assert "generate.py" in argv
    assert "--nproc_per_node=4" not in argv
    assert "--dit_fsdp" not in argv
    assert "--t5_fsdp" not in argv
    assert "--t5_cpu" in argv
    assert "--ulysses_size" in argv and "1" in argv
    assert "--frame_num" in argv and "5" in argv
    assert "--offload_model" in argv


# --- diagnostic : LingBot refuse tant que l'environnement manque -----------


def test_diagnostiquer_refuse_lingbot_sans_torch_ni_poids():
    etat = diagnostiquer(
        vram_libre_mb=8000.0,
        modules={"torch": False, "flash_attn": False},
        racine_poids=Path("Z:/absent-lingbot"),
    )
    assert etat["vram_ok"] is True
    assert etat["torch"] is False
    assert etat["flash_attn"] is False
    assert etat["poids_dit"] is False
    assert etat["poids_t5"] is False
    assert etat["poids_vae"] is False
    assert etat["run_lingbot"] is False
    assert etat["run_bouchon"] is True


def test_diagnostiquer_vram_sous_seuil_bloque_bouchon_et_lingbot():
    etat = diagnostiquer(
        vram_libre_mb=2400.0,
        modules={"torch": True, "flash_attn": True},
        racine_poids=Path("Z:/absent-lingbot"),
    )
    assert etat["vram_ok"] is False
    assert etat["run_bouchon"] is False
    assert etat["run_lingbot"] is False
    assert etat["vram_libre_mb"] == pytest.approx(2400.0)
    assert etat["seuil_vram_mb"] == pytest.approx(VRAM_ESTIMEE_MB)


def test_diagnostiquer_trouve_les_poids_sils_sont_la(tmp_path: Path):
    (tmp_path / "model-00001-of-00006.safetensors").write_bytes(b"x")
    (tmp_path / T5_CHECKPOINT).write_bytes(b"x")
    (tmp_path / VAE_CHECKPOINT).write_bytes(b"x")
    etat = diagnostiquer(
        vram_libre_mb=8000.0,
        modules={"torch": True, "flash_attn": True},
        racine_poids=tmp_path,
    )
    assert etat["poids_dit"] is True
    assert etat["poids_t5"] is True
    assert etat["poids_vae"] is True
    assert etat["run_lingbot"] is True


# --- 1 image bouchon -------------------------------------------------------


def test_produire_image_ecrit_un_png_832x480(tmp_path: Path):
    cible = tmp_path / "une.png"
    produit = produire_image(cible)
    assert produit == cible
    assert cible.is_file()
    assert _png_taille(cible) == (832, 480)


def test_bouchon_rgb_rend_4_frames_pleines():
    chunk = BouchonRgb().step({"text_event": "il pleut"})
    assert chunk.pas == 4
    assert chunk.mute is True
    assert len(chunk.frames) == 4
    assert all(len(trame) == LARGEUR * HAUTEUR * 3 for trame in chunk.frames)


def test_tenter_run_vram_ok_ecrit_une_image_et_un_evenement_muet(tmp_path: Path):
    resultat = tenter_run(vram_libre_mb=8000.0, dossier=tmp_path)
    assert resultat["mode"] == "bouchon"
    assert resultat["lingbot"] is False
    image = Path(resultat["image"])
    assert image.is_file()
    assert _png_taille(image) == (832, 480)
    evenement = resultat["evenement"]
    assert evenement["type"] == "world_frame"
    assert "frames" not in evenement
    assert evenement["mute"] is True
    assert len(evenement["images"]) == 4


def test_tenter_run_vram_ko_leve_sans_ecrire(tmp_path: Path):
    with pytest.raises(VramInsuffisante):
        tenter_run(vram_libre_mb=2400.0, dossier=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_evenement_du_bouchon_ne_ressemble_pas_a_de_l_audio():
    chunk = BouchonRgb().step({})
    evenement = vers_evenement(chunk)
    assert "frames" not in evenement
    assert "audio" not in evenement
    assert evenement["type"] == "world_frame"


# --- isolation -------------------------------------------------------------


def test_recette_n_importe_ni_torch_ni_hostagent_ni_ears():
    source = RECETTE_PY.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    importes: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                importes.add(alias.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            importes.add(noeud.module.split(".")[0])
            if noeud.module.startswith("src."):
                importes.add(noeud.module)

    for interdit in ("torch", "transformers", "flash_attn", "sounddevice"):
        assert interdit not in importes
    for interdit in (
        "src.brain",
        "src.ears",
        "src.mouth",
        "src.hostagent",
        "native.hostagent",
    ):
        assert interdit not in importes
        assert not any(nom.startswith(interdit + ".") for nom in importes)
