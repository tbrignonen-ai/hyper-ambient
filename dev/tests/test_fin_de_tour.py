"""Fin de tour sémantique (séance du 24/09, notes voix/UX).

Le silence seul coupe « Alors demain je voudrais… » au milieu de la pensée.
En mains libres, une transcription qui sonne inachevée attend le segment
suivant (2 s au plus) au lieu de partir au cerveau.
"""
from src.ears.fin_de_tour import enonce_incomplet


def test_phrases_inachevees():
    for phrase in (
        "Alors demain je voudrais...",
        "Euh… attends.",
        "Tu peux me chercher ça et",
        "Demande à Codex de compter les fichiers dans le",
        "Je pense que,",
        "Euh.",
        "Est-ce que",
    ):
        assert enonce_incomplet(phrase), phrase


def test_phrases_completes():
    for phrase in (
        "Quelle est la météo demain ?",
        "Demande à Codex de compter les répertoires.",
        "Merci.",
        "Bonjour.",
        "Tu m'entends ?",
        "",
    ):
        assert not enonce_incomplet(phrase), phrase


def test_le_tour_vocal_met_en_suspens_avant_le_cerveau():
    import inspect

    from dev.scripts import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "enonce_incomplet(prompt)" in source
    assert source.index("enonce_incomplet(prompt)") < source.index("self._memoire.doit_fermer(")


def test_sans_suite_l_enonce_part_seul_et_force_le_tour(monkeypatch):
    import asyncio

    from dev.scripts import serve_hostagent

    monkeypatch.setattr(serve_hostagent, "DELAI_SUSPENS_S", 0.01)
    pipeline = serve_hostagent.HostPipeline()
    vus = []

    async def tour(frames, websocket):
        vus.append((list(frames), pipeline._forcer_tour))

    pipeline._tour = tour
    pipeline._frames_en_suspens = ["t1", "t2"]
    asyncio.run(pipeline._liberer_suspens(None))
    assert vus == [(["t1", "t2"], True)]
    assert pipeline._frames_en_suspens == []


def test_silence_de_fin_de_tour_raccourci(monkeypatch):
    """Les énoncés inachevés sont protégés côté host-agent : le silence qui
    clôt un tour complet descend de 1200 à 800 ms."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from native.hostagent import windows_audio

    monkeypatch.delenv("TURN_SILENCE_MS", raising=False)
    assert windows_audio._silence_ms_tour() == 800.0
