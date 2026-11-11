"""« Quelle heure est-il ? » se répond sur l'horloge de Paris, sans cerveau."""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from src.mouth.horloge import demande_d_heure, phrase_heure
from src.temps import maintenant_local


def test_l_heure_est_une_demande_courte():
    for phrase in (
        "Quelle heure est-il ?",
        "Il est quelle heure ?",
        "Tu as l'heure ?",
        "What time is it?",
        "¿Qué hora es?",
    ):
        assert demande_d_heure(phrase), phrase


def test_un_calcul_horaire_reste_au_cerveau():
    for phrase in (
        "Il est 14 h 40, je finis à quelle heure ?",
        "À quelle heure commence la réunion ?",
        "Quelle heure est-il dans vingt minutes ?",
        "Demande à Codex l'heure de la démo.",
        "",
    ):
        assert not demande_d_heure(phrase), phrase


def test_l_ete_et_l_hiver_suivent_paris():
    ete = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    hiver = datetime(2026, 11, 11, 13, 5, tzinfo=timezone.utc)
    assert maintenant_local(ete).utcoffset() == timedelta(hours=2)
    assert maintenant_local(hiver).utcoffset() == timedelta(hours=1)
    assert phrase_heure(ete, "fr") == "Il est quatorze heures."
    assert phrase_heure(hiver, "fr") == "Il est quatorze heures cinq."
    assert phrase_heure(ete, "en") == "It's fourteen o'clock."
    assert "14" in phrase_heure(hiver, "es")


def test_midi_et_minuit_ont_leur_nom():
    midi = datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc)
    minuit = datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)
    assert phrase_heure(midi, "fr") == "Il est midi."
    assert phrase_heure(minuit, "fr") == "Il est minuit."


def test_le_tour_vocal_dit_l_heure_avant_le_cerveau():
    from dev.tests.test_hostagent_env_local import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "demande_d_heure(prompt)" in source
    assert source.index("demande_d_heure(prompt)") < source.index("self._memoire.doit_fermer(")
    assert serve_hostagent.maintenant_local is maintenant_local
