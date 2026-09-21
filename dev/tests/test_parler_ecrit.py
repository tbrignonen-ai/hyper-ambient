"""Chemin écrit : même montage cerveau que le tour vocal, sans EARS ni MOUTH."""
from __future__ import annotations

import asyncio
import functools
import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

RACINE = Path(__file__).resolve().parents[2]


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def _charger(nom, chemin):
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for manque in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(manque, MagicMock(name=manque))
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger(
    "serve_hostagent_parler_ecrit",
    RACINE / "dev" / "scripts" / "serve_hostagent.py",
)
parler_ecrit = _charger(
    "parler_ecrit",
    RACINE / "dev" / "scripts" / "parler_ecrit.py",
)


def test_monter_cerveau_est_partage():
    assert hasattr(serve_hostagent, "monter_cerveau")
    assert hasattr(parler_ecrit, "monter_cerveau")
    assert inspect.getsource(parler_ecrit.monter_cerveau) == inspect.getsource(
        serve_hostagent.monter_cerveau
    )
    source = inspect.getsource(serve_hostagent.HostPipeline.load)
    assert "monter_cerveau" in source


def test_flux_cerveau_est_partage():
    assert hasattr(serve_hostagent, "flux_cerveau")
    assert hasattr(parler_ecrit, "flux_cerveau")
    assert inspect.getsource(parler_ecrit.flux_cerveau) == inspect.getsource(
        serve_hostagent.flux_cerveau
    )
    source = inspect.getsource(serve_hostagent.HostPipeline._flux_brain)
    assert "flux_cerveau" in source
    assert "tool_choice" not in source


class _Brain:
    name = "double"

    def __init__(self):
        self.appels = []

    async def query_streaming(self, prompt, **kw):
        self.appels.append({"prompt": prompt, **kw})
        yield {"delta": "Je vais bien.", "stop_reason": None, "ttft_ms": 4.0, "channel": "reflex"}
        yield {"delta": "", "stop_reason": "stop", "ttft_ms": None, "channel": "reflex"}


@runs_async
async def test_tour_ecrit_affiche_canal_et_duree(tmp_path, capsys):
    from src.brain.tools import ToolRegistry
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats

    pieces = {
        "brain": _Brain(),
        "registre": ToolRegistry(),
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    compte = await parler_ecrit.jouer_tour_ecrit("Bonjour, comment vas-tu ?", pieces)
    sortie = capsys.readouterr().out
    assert compte["canal"] == "reflex"
    assert "reflex" in sortie
    assert "ms" in sortie
    assert "Je vais bien." in sortie
    texte = pieces["journal"].read_text(encoding="utf-8")
    assert "Bonjour, comment vas-tu ?" in texte
    assert "Je vais bien." in texte


class _BrainOutil:
    name = "double"

    async def query_streaming(self, prompt, **kw):
        from src.brain.tools import ToolCall

        yield {
            "delta": "",
            "stop_reason": "tool_calls",
            "ttft_ms": None,
            "channel": "deep",
            "tool_calls": [
                ToolCall(
                    id="c1",
                    name="ask_codex",
                    arguments={
                        "question": "Liste tous les fichiers Python dans src/brain"
                    },
                    raw_arguments='{"question":"Liste tous les fichiers Python dans src/brain"}',
                )
            ],
        }


@runs_async
async def test_tour_ecrit_affiche_la_question_reformulee(tmp_path, capsys):
    """Le prompt brut ne doit pas remplacer la question du modèle."""
    from src.brain.tools import ToolRegistry, ToolSpec
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats

    async def handler(question: str) -> str:
        return "Je demande à Codex. Je te préviens dès qu'il répond."

    registre = ToolRegistry()

    class _Mandat:
        registre_mandats = True

        async def __call__(self, question: str) -> str:
            return await handler(question)

    registre.register(
        ToolSpec(
            name="ask_codex",
            description="x",
            parameters={"type": "object", "properties": {}, "required": []},
            danger="read",
            handler=_Mandat(),
        )
    )
    pieces = {
        "brain": _BrainOutil(),
        "registre": registre,
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    prompt = "Demande a Codex combien de fichiers Python contient le dossier src/brain."
    compte = await parler_ecrit.jouer_tour_ecrit(prompt, pieces)
    sortie = capsys.readouterr().out
    assert "Liste tous les fichiers Python dans src/brain" in sortie
    assert f"→ Codex : {prompt}" not in sortie
    assert compte["canal"] == "deep"
    assert "[deep" in sortie
    assert "[reflex" not in sortie


class _BrainFillerPuisOutil:
    name = "double"

    async def query_streaming(self, prompt, **kw):
        from src.brain.tools import ToolCall

        yield {
            "delta": "Un instant.",
            "stop_reason": None,
            "ttft_ms": 10.0,
            "channel": "filler",
            "flush": True,
        }
        yield {
            "delta": "",
            "stop_reason": "tool_calls",
            "ttft_ms": None,
            "channel": "deep",
            "tool_calls": [
                ToolCall(
                    id="c1",
                    name="ask_codex",
                    arguments={"question": "compte les .py de src/brain"},
                    raw_arguments='{"question":"compte les .py de src/brain"}',
                )
            ],
        }


@runs_async
async def test_canal_prend_le_premier_morceau_porteur(tmp_path, capsys):
    """Filler + outil = escalade. Le libellé ne doit pas rester reflex."""
    from src.brain.tools import ToolRegistry, ToolSpec
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats

    registre = ToolRegistry()

    class _Mandat:
        registre_mandats = True

        async def __call__(self, question: str) -> str:
            return "Je demande à Codex. Je te préviens dès qu'il répond."

    registre.register(
        ToolSpec(
            name="ask_codex",
            description="x",
            parameters={"type": "object", "properties": {}, "required": []},
            danger="read",
            handler=_Mandat(),
        )
    )
    pieces = {
        "brain": _BrainFillerPuisOutil(),
        "registre": registre,
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    compte = await parler_ecrit.jouer_tour_ecrit("Demande a Codex de compter.", pieces)
    sortie = capsys.readouterr().out
    assert compte["canal"] == "deep"
    assert "[deep" in sortie
    assert "[reflex" not in sortie


class _BrainTroisAnnonces:
    name = "double"

    async def query_streaming(self, prompt, **kw):
        from src.brain.tools import ToolCall

        yield {
            "delta": "Un instant.",
            "stop_reason": None,
            "ttft_ms": 10.0,
            "channel": "filler",
            "flush": True,
        }
        yield {
            "delta": "Je vais demander à Codex de regarder ça pour toi.",
            "stop_reason": None,
            "ttft_ms": None,
            "channel": "deep",
        }
        yield {
            "delta": "",
            "stop_reason": "tool_calls",
            "ttft_ms": None,
            "channel": "deep",
            "tool_calls": [
                ToolCall(
                    id="c1",
                    name="ask_codex",
                    arguments={"question": "Quelle version de Python ?"},
                    raw_arguments='{"question":"Quelle version de Python ?"}',
                )
            ],
        }


@runs_async
async def test_une_seule_annonce_d_attente_sur_un_mandat(tmp_path, capsys):
    """Amorce + phrase du modèle + accusé = du bafouillage. Il en faut une."""
    from src.brain.tools import ToolRegistry, ToolSpec
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats, phrase_depot

    registre = ToolRegistry()

    class _Mandat:
        registre_mandats = True

        async def __call__(self, question: str) -> str:
            return phrase_depot("Codex")

    registre.register(
        ToolSpec(
            name="ask_codex",
            description="x",
            parameters={"type": "object", "properties": {}, "required": []},
            danger="read",
            handler=_Mandat(),
        )
    )
    pieces = {
        "brain": _BrainTroisAnnonces(),
        "registre": registre,
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    compte = await parler_ecrit.jouer_tour_ecrit(
        "Demande a Codex quelle version de Python.", pieces
    )
    sortie = capsys.readouterr().out
    attendue = phrase_depot("Codex")
    assert sortie.count("Un instant.") == 0
    assert "Je vais demander à Codex" not in sortie
    assert attendue in compte["texte"]
    assert compte["texte"].count(attendue) == 1
    assert "instant.Je" not in compte["texte"]
    assert "toi.Je" not in compte["texte"]


@runs_async
async def test_cursor_non_branche_affiche_la_phrase_sans_mandat(tmp_path, capsys):
    """Le chemin écrit ne saisit pas Codex quand on a nommé Cursor."""
    from src.brain.tools import ToolRegistry, ToolSpec
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats, phrase_si_harnais_non_branche

    async def interdit(question: str) -> str:
        raise AssertionError("Codex ne doit pas être saisi")

    class _Mandat:
        registre_mandats = True

        async def __call__(self, question: str) -> str:
            return await interdit(question)

    registre = ToolRegistry()
    registre.register(
        ToolSpec(
            name="ask_codex",
            description="x",
            parameters={"type": "object", "properties": {}, "required": []},
            danger="read",
            handler=_Mandat(),
        )
    )
    pieces = {
        "brain": _BrainOutil(),
        "registre": registre,
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    prompt = "Demande a Cursor de me resumer src/brain/router.py."
    attendue = phrase_si_harnais_non_branche(prompt, registre)
    compte = await parler_ecrit.jouer_tour_ecrit(prompt, pieces)
    sortie = capsys.readouterr().out
    assert attendue
    assert attendue in compte["texte"]
    assert attendue in sortie
    assert "→ Codex" not in sortie
    assert pieces["mandats"].en_cours() == []


def test_recoller_prononce_ajoute_l_espace_a_la_couture():
    """La jointure vit à la concaténation, pas à la fin de chaque libellé."""
    recoller = serve_hostagent.recoller_prononce
    assert recoller(["Un instant.", "Je demande à Codex."]) == (
        "Un instant. Je demande à Codex."
    )
    assert recoller(["Hel", "lo"]) == "Hello"
    assert recoller(["Déjà un espace. ", "Suite."]) == "Déjà un espace. Suite."


@runs_async
async def test_tour_sans_mandat_n_est_pas_affecte(tmp_path, capsys):
    from src.brain.tools import ToolRegistry
    from src.gate.permission import Gate
    from src.brain.mandat import RegistreMandats

    pieces = {
        "brain": _Brain(),
        "registre": ToolRegistry(),
        "porte": Gate(mode="auto"),
        "mandats": RegistreMandats(),
        "historique": [],
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    compte = await parler_ecrit.jouer_tour_ecrit("Bonjour, comment vas-tu ?", pieces)
    sortie = capsys.readouterr().out
    assert compte["texte"] == "Je vais bien."
    assert "détail est dans" not in sortie.lower()
    assert "detail est dans" not in sortie.lower()
    assert pieces["mandats"].en_cours() == []
    assert pieces["mandats"].prets() == []


@runs_async
async def test_annonce_mandat_riche_prononce_l_invitation(tmp_path, capsys):
    from src.brain.contrat_harnais import ReponseHarnais
    from src.brain.mandat import Mandat, RegistreMandats, phrase_arrivee

    pieces = {
        "mandats": RegistreMandats(),
        "journal": tmp_path / "convo.md",
    }
    pieces["journal"].write_text("# test\n\n", encoding="utf-8")
    mandat = Mandat(
        identifiant="m1",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=0.0,
        etat="fini",
        reponse=ReponseHarnais(
            verdict="fait",
            resume_voix="Le routeur departage local et distant.",
            detail_voix="d",
            resultat_complet="Y" * 4000,
            conforme=True,
        ),
    )
    pieces["mandats"].deposer(mandat)
    await parler_ecrit._annoncer_mandat(pieces, mandat)
    sortie = capsys.readouterr().out
    attendue = phrase_arrivee(mandat)
    assert attendue in sortie
    assert "Le détail est dans Codex" in attendue or "Le detail est dans Codex" in attendue
