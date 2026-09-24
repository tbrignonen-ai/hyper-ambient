"""Répéter la dernière réponse sans passer par le modèle (séance du 24 sept).

« Je n'ai pas entendu ta réponse. » après « Codex a fini. 22 » donnait
« Je suis là. », puis, avec une consigne explicite, « je n'ai pas entendu
votre demande précédente » : le 3B ne suit pas. La décision est donc locale.
"""
from src.mouth.repetition import demande_de_repetition, derniere_reponse


def test_demandes_de_repetition_reconnues():
    for phrase in (
        "Je n'ai pas entendu ta réponse.",
        "J'ai pas compris.",
        "Tu peux répéter ?",
        "Répète.",
        "Redis-moi ça",
        "Qu'est-ce que tu as dit ?",
        "Sorry, I didn't hear you.",
        "Can you repeat that?",
    ):
        assert demande_de_repetition(phrase), phrase


def test_vraies_demandes_non_confondues():
    for phrase in (
        "Répète après moi que la réunion est à dix heures et envoie ça à Codex pour qu'il le note",
        "Quelle heure est-il ?",
        "Demande à Codex de compter les répertoires.",
        "",
    ):
        assert not demande_de_repetition(phrase), phrase


def test_derniere_reponse_prend_le_dernier_message_assistant():
    historique = [
        {"role": "user", "content": "(Tâche confiée à Codex) q"},
        {"role": "assistant", "content": "Codex a fini. 22\ndetail long"},
    ]
    assert derniere_reponse(historique) == "Codex a fini. 22"
    assert derniere_reponse([]) is None


def test_le_tour_vocal_repete_sans_appeler_le_cerveau():
    import inspect

    from dev.scripts import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "demande_de_repetition(prompt)" in source
    # La répétition part avant tout appel au cerveau.
    assert source.index("demande_de_repetition(prompt)") < source.index("self._memoire.doit_fermer(")


def test_question_sur_la_reponse_du_harnais_rend_son_resultat():
    """Séance du 24/09 : « Codex a fini. 3 fois 8 font 24. » puis « Codex, il
    a dit quoi là ? » → « Je ne sais pas » (1 fois sur 3 au banc)."""
    from src.mouth.repetition import demande_resultat_harnais, dernier_resultat_harnais

    for phrase in (
        "Ecodex il a dit quoi là ?",
        "Qu'est-ce qu'il a répondu ?",
        "Qu'a dit Codex ?",
        "C'était quoi la réponse de Claude ?",
        "Codex a répondu quoi ?",
    ):
        assert demande_resultat_harnais(phrase), phrase
    assert not demande_resultat_harnais("Demande à Codex ce qu'il pense de ce fichier")

    historique = [
        {"role": "user", "content": "(Tâche confiée à Codex) 3 x 8"},
        {"role": "assistant", "content": "Codex a fini. 3 fois 8 font 24.\ndetail"},
        {"role": "user", "content": "merci"},
        {"role": "assistant", "content": "De rien."},
    ]
    assert dernier_resultat_harnais(historique) == "Codex a fini. 3 fois 8 font 24."
    assert dernier_resultat_harnais([]) is None
