"""Branchement JeV au host-agent : repli bouton, jamais d'envoi harnais."""
from __future__ import annotations

from src.ears.jev_reflexe import JevEvaluation, JevSignals
from test_hostagent_env_local import serve_hostagent


def _evaluation(*, addressed: bool, harness: str | None = None) -> JevEvaluation:
    return JevEvaluation(
        answers={},
        signals=JevSignals(
            addressed_to_mother=addressed,
            real_interruption=False,
            phrase_finished=True,
            transcription_uncertain=False,
            expected_response_length="few_sentences",
            tone="calm",
            frustration=None,
            needs_current_information=False,
            refers_to_context=False,
            requests_memory=False,
            sensitive_local_action=False,
            contains_personal_data=False,
            named_harness=harness,
        ),
    )


def test_sans_evaluation_le_bouton_reste():
    """Pas de clé / timeout / erreur → None → le tour continue comme le bouton."""
    assert serve_hostagent.jev_ignore_tour(None) is False


def test_non_adresse_a_mother_ignore_le_tour():
    assert serve_hostagent.jev_ignore_tour(_evaluation(addressed=False)) is True


def test_adresse_a_mother_continue_le_tour():
    assert serve_hostagent.jev_ignore_tour(_evaluation(addressed=True)) is False


def test_harnais_nomme_n_envoie_aucune_tache():
    """Observation seulement : un harnais nommé ne déclenche pas d'ignore ni d'envoi."""
    evaluation = _evaluation(addressed=True, harness="codex")
    assert serve_hostagent.jev_ignore_tour(evaluation) is False
    assert evaluation.signals.named_harness == "codex"


def test_typesafe_api_key_injectee_depuis_env_local(tmp_path):
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(b"TYPESAFE_API_KEY=cle-jev-test\r\nCODEX_BRIDGE_TOKEN=jeton-ok\n")
    env: dict[str, str] = {}
    injectees = serve_hostagent.charger_env_local(chemin=chemin, environ=env)
    assert "TYPESAFE_API_KEY" in injectees
    assert env["TYPESAFE_API_KEY"] == "cle-jev-test"
    assert "\r" not in env["TYPESAFE_API_KEY"]
