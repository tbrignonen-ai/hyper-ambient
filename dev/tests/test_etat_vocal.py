"""« Tu fonctionnes ? » se répond sans cerveau, depuis le relevé de santé."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from src.mouth.etat_vocal import _PHRASES, demande_d_etat, lire_etat, phrase_d_etat


def test_la_question_de_service_est_reconnue():
    for phrase in (
        "Tu fonctionnes ?",
        "Est-ce que tout fonctionne ?",
        "État du système.",
        "Are you up?",
        "¿Estás en línea?",
    ):
        assert demande_d_etat(phrase), phrase


def test_la_conversation_ordinaire_n_est_pas_un_releve():
    for phrase in (
        "Ça va ?",
        "Comment tu vas ?",
        "Explique pourquoi tu fonctionnes mal depuis la mise à jour d'hier soir",
        "Demande à Codex si le pont fonctionne.",
        "",
    ):
        assert not demande_d_etat(phrase), phrase


def test_sans_releve_on_ne_pretend_pas_que_tout_va_bien(tmp_path):
    assert phrase_d_etat(None) == _PHRASES["fr"]["absent"]
    assert phrase_d_etat(lire_etat(tmp_path / "absent.json")) == _PHRASES["fr"]["absent"]
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text("{", encoding="utf-8")
    assert lire_etat(mauvais) is None


def test_un_pont_muet_est_dit_avec_la_phrase_du_worker():
    snapshot = {
        "healthStatus": "DEGRADED",
        "alertMessage": "Le pont vers Codex ne répond plus, je continue en local.",
        "degradedComponents": "pont_codex",
    }
    assert phrase_d_etat(snapshot) == snapshot["alertMessage"]
    assert "Codex" in phrase_d_etat(snapshot, "en")
    assert phrase_d_etat({"healthStatus": "UP"}) == _PHRASES["fr"]["ok"]


def test_les_phrases_francaises_suivent_le_worker():
    import sys

    worker = Path(__file__).resolve().parents[2] / "workers" / "night_health_vault_note"
    sys.path.insert(0, str(worker))
    from handlers import PHRASES_ALERTE

    for ident, phrase in PHRASES_ALERTE.items():
        assert _PHRASES["fr"][ident] == phrase


def test_les_trois_langues_ont_les_memes_cles():
    assert set(_PHRASES) == {"fr", "en", "es"}
    reference = set(_PHRASES["fr"])
    for table in _PHRASES.values():
        assert set(table) == reference


def test_le_tour_vocal_repond_avant_le_cerveau():
    from dev.tests.test_hostagent_env_local import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "demande_d_etat(prompt)" in source
    assert source.index("demande_d_etat(prompt)") < source.index("self._memoire.doit_fermer(")


def test_un_snapshot_ecrit_se_relit(tmp_path):
    chemin = tmp_path / "sante.json"
    chemin.write_text(
        json.dumps({"healthStatus": "UP", "alertMessage": ""}),
        encoding="utf-8",
    )
    assert lire_etat(chemin)["healthStatus"] == "UP"
