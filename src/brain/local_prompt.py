"""Prompt système du cerveau local.

Le prompt vocal historique reste possédé par MOUTH. Le cerveau local a en
plus une identité produit et des règles de sortie explicites, appliquées ici
au dernier point avant l'envoi à llama-server.
"""

from pathlib import Path

_ICI = Path(__file__).resolve().parent


def _lire(nom: str) -> str:
    # Les consignes de conversation vivent dans un fichier unique, lu par le
    # cerveau local ET le distant (séance du 24/09 : « une sorte d'agent.md »).
    return (_ICI / nom).read_text(encoding="utf-8").strip()


LOCAL_SYSTEM_PROMPT = _lire("conversation.fr.md")
LOCAL_SYSTEM_PROMPT_EN = _lire("conversation.en.md")
