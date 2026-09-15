"""WorldPort : peripherique visuel muet, jamais un cerveau.

Le world n'entend rien, ne parle pas, et ne raisonne pas. BRAIN lui envoie
des actions et des evenements texte ; il rend des images 480p. Le processus
est optionnel et separe : s'il n'a pas assez de VRAM, il ne demarre pas.

Aucun test ici ne charge LingBot, ni torch, ni flash-attn. Le backend par
defaut est un bouchon. Ce qui est prouve, c'est le contrat start / step /
stop / budget, le silence (pas d'audio), la surface d'actions fermee, et
les cinq criteres de mesure du sprint du 11 septembre.

Ce qui n'est pas prouve ici : un run 1.3B mono-GPU. Le README amont ne
montre que du 480P multi-GPU. Tant que nvidia-smi n'a pas mesure le world
seul, le budget reste une estimation.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.world.port import (
    ACTION_KEYS,
    CRITERES_MESURE,
    HAUTEUR,
    LARGEUR,
    LICENCE,
    MODELE_ID,
    PAS_PAR_CHUNK,
    PLAFOND_VRAM_MB,
    T5_DEVICE,
    VRAM_ESTIMEE_MB,
    ActionInconnue,
    AudioInterdit,
    SessionAbsente,
    SessionDejaOuverte,
    VramInconnue,
    VramInsuffisante,
    WorldPort,
    lire_vram_libre_mb,
    verdict_coloc,
    vers_evenement,
)


ROOT = Path(__file__).resolve().parents[2]
PORT_PY = ROOT / "src" / "world" / "port.py"


def _port(**kw) -> WorldPort:
    kw.setdefault("vram_libre_mb", 8000.0)
    return WorldPort(**kw)


# --- VRAM : ne jamais demarrer a l'aveugle --------------------------------


def test_start_refuse_si_vram_sous_le_seuil():
    lanceur = _Lanceur()
    port = WorldPort(vram_libre_mb=2400.0, lanceur=lanceur)

    with pytest.raises(VramInsuffisante):
        port.start("un lac au pied des montagnes")

    assert lanceur.appels == 0


def test_start_refuse_si_vram_inconnue():
    def boom(_argv):
        raise FileNotFoundError("nvidia-smi")

    port = WorldPort(executeur_vram=boom)

    with pytest.raises(VramInconnue):
        port.start("un lac")


def test_vram_injectee_court_circuite_nvidia_smi():
    appels: list = []

    def spy(argv):
        appels.append(list(argv))
        return "0"

    port = WorldPort(vram_libre_mb=8000.0, executeur_vram=spy)
    port.start("un lac")
    assert appels == []


def test_lire_vram_parse_la_sortie_nvidia_smi():
    def fake(_argv):
        return "2361\n"

    assert lire_vram_libre_mb(executeur=fake) == pytest.approx(2361.0)


# --- start / session -------------------------------------------------------


def test_start_avec_prompt_ouvre_une_session_muette():
    session = _port().start("un lac calme sous un ciel bleu")

    assert session.prompt == "un lac calme sous un ciel bleu"
    assert session.mute is True
    assert session.width == LARGEUR
    assert session.height == HAUTEUR


def test_start_accepte_une_image_en_octets():
    session = _port().start(b"\xff\xd8\xff")  # JPEG tronque, on n'en decode rien

    assert session.prompt == ""
    assert session.image is True
    assert session.mute is True


def test_prompt_vide_est_refuse():
    with pytest.raises(ValueError):
        _port().start("")
    with pytest.raises(ValueError):
        _port().start("   ")


def test_seconde_session_sans_stop_est_refusee():
    port = _port()
    port.start("un lac")
    with pytest.raises(SessionDejaOuverte):
        port.start("une foret")


def test_processus_separe_est_le_defaut():
    assert WorldPort(vram_libre_mb=8000.0).processus_separe is True


def test_processus_in_process_reste_possible():
    port = _port(processus_separe=False)
    port.start("un lac")
    chunk = port.step({"text_event": "il commence a pleuvoir"})
    assert chunk.mute is True
    assert port.processus_separe is False


def test_start_avec_assez_de_vram_appelle_le_lanceur_une_fois():
    lanceur = _Lanceur()
    port = _port(lanceur=lanceur)
    port.start("un lac")
    assert lanceur.appels == 1


# --- step : chunk 480p, 4 pas, muet ----------------------------------------


def test_step_sans_session_est_refuse():
    with pytest.raises(SessionAbsente):
        _port().step({"text_event": "il pleut"})


def test_step_retourne_un_chunk_480p_de_4_pas():
    port = _port()
    port.start("un lac")
    chunk = port.step({"camera": {"yaw": 0.1}, "move": {"forward": 0.2}})

    assert chunk.width == 832
    assert chunk.height == 480
    assert chunk.pas == 4
    assert chunk.pas == PAS_PAR_CHUNK
    assert len(chunk.frames) == 4


def test_le_chunk_est_muet():
    port = _port()
    port.start("un lac")
    chunk = port.step({"text_event": "un oiseau s'envole"})

    assert chunk.mute is True
    assert chunk.audio is None


def test_scene_continue_sans_action():
    port = _port()
    port.start("un lac")
    chunk = port.step({})
    assert len(chunk.frames) == 4
    assert chunk.mute is True


def test_evenement_texte_pilote_un_pas():
    port = _port()
    port.start("un lac")
    chunk = port.step({"text_event": "il commence a pleuvoir"})
    assert chunk.pas == 4
    assert port.derniere_action["text_event"] == "il commence a pleuvoir"


# --- surface d'actions fermee, audio interdit ------------------------------


def test_action_audio_est_refusee():
    port = _port()
    port.start("un lac")
    for cle, valeur in (
        ("audio", b"\x00\x01"),
        ("pcm", [0.0, 0.1]),
        ("wav", b"RIFF"),
        ("samples", [0.0]),
    ):
        with pytest.raises(AudioInterdit):
            port.step({cle: valeur})


def test_cle_action_inconnue_est_refusee():
    port = _port()
    port.start("un lac")
    with pytest.raises(ActionInconnue):
        port.step({"combat": "attaque"})
    assert ACTION_KEYS == frozenset({"camera", "move", "text_event"})


# --- stop ------------------------------------------------------------------


def test_stop_ferme_la_session():
    port = _port()
    port.start("un lac")
    port.stop()
    with pytest.raises(SessionAbsente):
        port.step({"move": {"forward": 1.0}})


def test_stop_sans_session_ne_leve_pas():
    _port().stop()


# --- budget + cinq criteres ------------------------------------------------


def test_budget_expose_vram_fps_latence():
    budget = _port().budget()
    assert set(budget) >= {"vram_mb", "fps", "latence_action_ms"}
    assert budget["vram_mb"] == pytest.approx(VRAM_ESTIMEE_MB)


def test_budget_sans_mesure_reste_estime():
    port = _port()
    port.start("un lac")
    port.step({"text_event": "il pleut"})
    budget = port.budget()
    assert budget["mesure"] is False
    assert budget["fps"] == 0.0
    assert budget["latence_action_ms"] == 0.0


def test_noter_mesure_bascule_le_budget_en_mesure():
    port = _port()
    port.noter_mesure(
        vram_mb=5600.0,
        fps=12.0,
        latence_action_ms=180.0,
        ram_hote_mb=11200.0,
    )
    budget = port.budget()
    assert budget["mesure"] is True
    assert budget["vram_mb"] == pytest.approx(5600.0)
    assert budget["fps"] == pytest.approx(12.0)
    assert budget["latence_action_ms"] == pytest.approx(180.0)
    assert budget["ram_hote_mb"] == pytest.approx(11200.0)


def test_criteres_de_mesure_sont_les_cinq_du_sprint():
    assert CRITERES_MESURE == (
        "vram_crete_world_seul_mb",
        "images_par_seconde_480p",
        "latence_action_image_ms",
        "ram_hote_t5_cpu_mb",
        "verdict_coloc_world_mouth_piper_reflexe_distant",
    )


def test_verdict_coloc_option2_tient_sous_10_go_en_estime():
    # Option 2 CHOIX : world 5.5 + STT 1.2 + MiniCPM 2.3 + overhead 0.5 = 9.5
    reste_stack = 1200.0 + 2300.0 + 500.0
    assert verdict_coloc(
        vram_world_mb=VRAM_ESTIMEE_MB,
        vram_reste_stack_mb=reste_stack,
    ) is True


def test_verdict_coloc_refuse_si_somme_depasse_le_plafond():
    assert verdict_coloc(vram_world_mb=6500.0, vram_reste_stack_mb=4000.0) is False


def test_plafond_vram_est_10_go():
    assert PLAFOND_VRAM_MB == 10000.0


# --- identite modele / licence / T5 CPU ------------------------------------


def test_licence_est_cc_by_nc_sa():
    assert LICENCE == "CC-BY-NC-SA-4.0"
    assert "nc" in LICENCE.lower()


def test_modele_est_le_1_3b_causal_fast():
    assert MODELE_ID == "robbyant/lingbot-world-v2-1.3b-causal-fast"


def test_t5_declare_sur_cpu():
    assert T5_DEVICE == "cpu"


def test_resolution_pleine_est_832x480():
    assert (LARGEUR, HAUTEUR) == (832, 480)


def test_vram_estimee_full_480p_est_5_5_go():
    assert VRAM_ESTIMEE_MB == 5500.0


# --- evenement presence : ne jamais ressembler a de l'audio ----------------


def test_l_evenement_presence_n_a_pas_de_cle_frames():
    """native/presence/app.py joue toute cle `frames` comme de l'audio.

    Le world passe par le canal de presence, mais avec un type distinct et
    sans cette cle — sinon la voix entendrait des pixels.
    """
    port = _port()
    port.start("un lac")
    evenement = vers_evenement(port.step({"text_event": "il pleut"}))
    assert "frames" not in evenement
    assert evenement["type"] == "world_frame"
    assert "images" in evenement


def test_l_evenement_presence_est_muet():
    port = _port()
    port.start("un lac")
    evenement = vers_evenement(port.step({}))
    assert evenement["mute"] is True
    assert "audio" not in evenement
    assert "pcm" not in evenement


# --- isolation : pas de MOUTH, EARS, BRAIN, torch --------------------------


def test_port_n_importe_ni_mouth_ni_ears_ni_brain_ni_torch():
    source = PORT_PY.read_text(encoding="utf-8")
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
    for interdit in ("src.brain", "src.ears", "src.mouth", "src.presence"):
        assert interdit not in importes
        assert not any(nom.startswith(interdit + ".") for nom in importes)


class _Lanceur:
    def __init__(self) -> None:
        self.appels = 0

    def __call__(self):
        self.appels += 1
        return object()
