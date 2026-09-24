"""Séance du 24 sept : trois répliques fausses tracées au prompt système.

- « Tadji Codex » → « Bonsoir Tadji Codex. » : le modèle recopie l'exemple
  « Lui : Bonsoir. / Toi : Bonsoir. » dès que la demande est floue.
- « Je n'ai pas entendu ta réponse. » → « Je suis là. » : rien ne lui dit
  de répéter.
- Correction d'une demande confiée à Codex → « Je compte les sous-dossiers »,
  sans rien renvoyer : elle affirme une action qu'elle ne fait pas.
"""
from src.brain.local_prompt import LOCAL_SYSTEM_PROMPT, LOCAL_SYSTEM_PROMPT_EN
from src.mouth.normalize import VOICE_SYSTEM_PROMPT


def test_aucun_exemple_de_salutation_a_recopier():
    assert "Bonsoir" not in VOICE_SYSTEM_PROMPT


def test_consignes_repeter_incompris_et_harnais_fideles():
    for prompt in (VOICE_SYSTEM_PROMPT, LOCAL_SYSTEM_PROMPT):
        bas = prompt.lower()
        assert "pas entendu" in bas and "répète" in bas
        assert "ne salue pas" in bas
        assert "sans la reformuler" in bas
    bas = LOCAL_SYSTEM_PROMPT_EN.lower()
    assert "didn't hear" in bas and "repeat" in bas
