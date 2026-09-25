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


def test_la_longueur_ne_decide_plus_c_est_le_classifieur():
    """25/09 : le distant sert aux harnais et aux questions difficiles. Une
    phrase de conversation, même longue, reste locale si le classifieur le dit ;
    le 3B répond désormais avec la consigne complète (mesuré le 25/09)."""
    from src.brain.router import RouterBrain

    class _Reponse:
        def __init__(self, verdict):
            self.verdict = verdict

        def json(self):
            return {"content": self.verdict}

    class _Client:
        def __init__(self, verdict):
            self.verdict = verdict

        async def post(self, *a, **k):
            return _Reponse(self.verdict)

    routeur = RouterBrain.__new__(RouterBrain)
    routeur.classifier = None
    routeur.classify_host = "http://x"
    routeur._client = _Client("REFLEXE")
    assert asyncio.run(routeur.classify("Je suis un peu stressé pour ma soutenance cet après-midi."))["route"] == "reflex"
    routeur._client = _Client("ESCALADE")
    assert asyncio.run(routeur.classify("Explique-moi la différence entre TCP et UDP."))["route"] == "escalate"
    # Nommer un harnais part toujours au distant, sans classifieur.
    routeur._client = _Client("REFLEXE")
    assert asyncio.run(routeur.classify("Dis à Codex bonjour."))["route"] == "escalate"
