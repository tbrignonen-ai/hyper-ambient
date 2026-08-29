"""Quand le tour precedent doit peser sur la classification, et quand il ne doit pas.

Le contexte a ete ajoute pour un cas precis : « vas-y », « et alors ? », un tour qui
ne veut rien dire seul. Mais l'injecter a chaque fois deregle le jugement de
difficulte. Observe en conditions reelles : la question horaire, qui escalade
correctement apres un tour vide, se fait classer REFLEXE quand la politesse du
tour precedent la precede, et recoit une reponse locale fausse.

La regle : un enonce qui se suffit a lui-meme se juge seul. Seul un enonce court,
donc probablement anaphorique, a besoin de ce qui precede.
"""
from src.brain.router import doit_joindre_contexte


def test_un_enonce_court_reclame_le_contexte():
    assert doit_joindre_contexte("vas-y")
    assert doit_joindre_contexte("et alors ?")
    assert doit_joindre_contexte("oui")


def test_une_question_complete_se_juge_seule():
    assert not doit_joindre_contexte(
        "Il est 14 heures 40, ma reunion commence dans 20 minutes "
        "et dure 40 minutes, a quelle heure je finis ?"
    )


def test_un_enonce_vide_ne_reclame_rien():
    assert not doit_joindre_contexte("")
    assert not doit_joindre_contexte("   ")
