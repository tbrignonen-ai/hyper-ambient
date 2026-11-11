"""« On est quel jour ? » se répond sur le calendrier de Paris, sans cerveau."""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

from src.mouth.calendrier import demande_de_date, phrase_date
from src.mouth.horloge import demande_d_heure


def test_la_date_est_une_demande_courte():
    for phrase in (
        "On est quel jour ?",
        "Quelle est la date ?",
        "On est le combien ?",
        "What day is it?",
        "What's the date?",
        "¿Qué día es?",
        "¿A qué fecha estamos?",
    ):
        assert demande_de_date(phrase), phrase


def test_un_calcul_de_date_reste_au_cerveau():
    for phrase in (
        "Dans trois jours, on sera quel jour ?",
        "Quelle est la date de la réunion ?",
        "Demande à Codex la date de la démo.",
        "What day is it tomorrow?",
        "Quelle heure est-il ?",
        "",
    ):
        assert not demande_de_date(phrase), phrase
    assert demande_d_heure("Quelle heure est-il ?")
    assert not demande_d_heure("On est quel jour ?")


def test_le_onze_novembre_et_le_premier():
    onze = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    premier = datetime(2026, 10, 31, 23, 30, tzinfo=timezone.utc)
    assert phrase_date(onze, "fr") == (
        "Nous sommes mercredi onze novembre deux mille vingt-six."
    )
    assert phrase_date(onze, "en") == (
        "It's Wednesday, November eleventh, two thousand twenty-six."
    )
    assert phrase_date(onze, "es") == (
        "Es miércoles, once de noviembre de dos mil veintiséis."
    )
    assert phrase_date(premier, "fr") == (
        "Nous sommes dimanche premier novembre deux mille vingt-six."
    )
    assert "first" in phrase_date(premier, "en")
    assert "primero" in phrase_date(premier, "es")


def test_le_tour_vocal_dit_la_date_avant_le_cerveau():
    from dev.tests.test_hostagent_env_local import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "demande_de_date(prompt)" in source
    assert source.index("demande_de_date(prompt)") < source.index(
        "self._memoire.doit_fermer("
    )
