"""C11 — identité et consignes du cerveau local Hyper Ambient."""

from src.brain.openai_compat import LlamaCppBrain


def test_cerveau_local_porte_identite_et_style_vocal():
    brain = LlamaCppBrain()

    payload = brain._payload("Bonjour", None, 0.2, True, None)
    system = payload["messages"][0]["content"]

    assert "Hyper Ambient" in system
    assert "français" in system
    assert "texte brut" in system
    assert "Markdown" in system
    # 24/09 : la consigne « réponse courte » rendait « Oui. » ; le fichier de
    # conversation interdit désormais la réponse d'un seul mot.
    assert "seul mot" in system
    assert "demande explicite" in system


def test_cerveau_local_remplace_le_prompt_dans_une_boucle_outils():
    brain = LlamaCppBrain()
    messages = [
        {"role": "system", "content": "ancien prompt"},
        {"role": "user", "content": "Cherche ceci"},
    ]

    payload = brain._payload(
        "Cherche ceci", None, 0.2, True, None, messages=messages, tools=[{"type": "function"}]
    )

    assert payload["messages"][0]["content"] != "ancien prompt"
    assert "Hyper Ambient" in payload["messages"][0]["content"]
    assert messages[0]["content"] == "ancien prompt"
