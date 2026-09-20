"""Contrat d'usage des outils du cerveau local, sans heuristique de mots-cles."""

from src.brain.openai_compat import LlamaCppBrain


def test_prompt_local_impose_la_verification_outil_des_questions_meta_et_actuelles():
    """Le prompt effectivement envoye rend l'appel d'outil prioritaire."""
    payload = LlamaCppBrain()._payload(
        "Peux-tu acceder au web ?",
        None,
        0.2,
        True,
        None,
        tools=[{"type": "function", "function": {"name": "web_search"}}],
    )

    system = payload["messages"][0]["content"].lower()
    assert "outil disponible peut vérifier" in system
    assert "question sur ton accès au web" in system
    assert "faits actuels ou susceptibles d'avoir changé" in system
