"""Consignes de conversation dans un fichier unique (séance du 24/09).

« Le modèle doit avoir des instructions de conversation, une sorte
d'agent.md. » Local et distant lisent le même fichier : un seul endroit pour
régler le ton, le fil, les mots mal entendus et les outils.
"""
import asyncio
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def test_les_deux_cerveaux_lisent_le_fichier_de_conversation():
    from src.brain.local_prompt import LOCAL_SYSTEM_PROMPT, LOCAL_SYSTEM_PROMPT_EN
    from src.mouth.normalize import VOICE_SYSTEM_PROMPT

    fr = (RACINE / "src/brain/conversation.fr.md").read_text(encoding="utf-8").strip()
    en = (RACINE / "src/brain/conversation.en.md").read_text(encoding="utf-8").strip()
    assert LOCAL_SYSTEM_PROMPT.strip() == fr
    assert VOICE_SYSTEM_PROMPT.strip() == fr
    assert LOCAL_SYSTEM_PROMPT_EN.strip() == en


def test_la_conversation_n_est_plus_telegraphique():
    fr = (RACINE / "src/brain/conversation.fr.md").read_text(encoding="utf-8").lower()
    assert "jamais de réponse d'un seul mot" in fr
    assert "reprends le fil" in fr


def test_une_phrase_de_cinq_mots_ne_part_jamais_au_local():
    """Le 3B répondait « Je suis là. », « Oui. », « J'ai du corps… »."""
    from src.brain.router import RouterBrain

    class _Reponse:
        def json(self):
            return {"content": "REFLEXE"}

    class _Client:
        async def post(self, *a, **k):
            return _Reponse()

    routeur = RouterBrain.__new__(RouterBrain)
    routeur._client = _Client()
    routeur.classify_host = "http://x"
    assert asyncio.run(routeur.classify("Dis un truc, j'ai du corps."))["route"] == "escalate"
    assert asyncio.run(routeur.classify("Je n'ai pas entendu ta réponse."))["route"] == "escalate"
    # Une formule courte reste au réflexe local.
    assert asyncio.run(routeur.classify("Merci beaucoup."))["route"] == "reflex"
