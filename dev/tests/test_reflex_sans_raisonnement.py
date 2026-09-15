"""
BRAIN : le reflexe local ne raisonne pas a voix basse.

MiniCPM5-2B est un modele a raisonnement. Mesure le 15 sept : 600 a 800
caracteres de `reasoning_content` par tour, un `content` vide ou tronque, et
sous budget il recopie le premier exemple du prompt (« Bonsoir. Ça va ? »).
Avec `enable_thinking: false`, reponse immediate et pertinente. Le canal
distant, lui, ne recoit pas ce champ : il n'a rien a en faire.
"""
from src.brain.openai_compat import LlamaCppBrain, OpenAICompatBrain


def _payload(brain):
    return brain._payload("Tu m'entends ?", "systeme", 0.7, True, None)


def test_reflexe_local_desactive_le_raisonnement():
    p = _payload(LlamaCppBrain())
    assert p["chat_template_kwargs"] == {"enable_thinking": False}


def test_canal_distant_ne_recoit_pas_le_champ():
    p = _payload(OpenAICompatBrain(api_endpoint="https://exemple.invalid/v1/chat/completions"))
    assert "chat_template_kwargs" not in p
