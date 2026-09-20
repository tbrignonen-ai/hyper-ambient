"""Fenetre de conversation : une fois nommee, elle reste engagee un moment.

Mesure du 2026-09-20 contre l'API JeV, sur les phrases reelles de l'utilisateur :

    0.64  « coucou tu es la ? »
    0.38  « bon je teste le mode main libre, bonjour »
    0.31  « bonjour »
    0.26  « et maintenant place au film de la soiree »   (television en fond)
    0.25  « salut »
    0.13  « bon alors on disait le module deux »          (conversation a cote)

« bonjour » et « salut » scorent SOUS une phrase de television : aucun seuil ne
peut les separer, et JeV n'a pas tort — un « bonjour » lance dans une piece ne
designe linguistiquement personne. Le reglage du seuil est donc epuise.

D'ou cette fenetre : on la nomme une fois, puis tout ce qui suit lui est adresse
pendant un court moment. C'est ainsi qu'on parle a quelqu'un, et c'est ainsi que
fonctionnent les assistants reels.
"""
from __future__ import annotations


def test_fenetre_ouverte_par_une_adresse_puis_expire():
    from src.ears.jev_reflexe import FenetreConversation

    f = FenetreConversation(duree_s=30.0)
    assert not f.engagee(maintenant=100.0)      # rien ne s'est encore passe

    f.engager(maintenant=100.0)
    assert f.engagee(maintenant=100.0)
    assert f.engagee(maintenant=129.9)          # juste avant l'echeance
    assert not f.engagee(maintenant=130.1)      # expiree


def test_chaque_tour_adresse_prolonge_la_fenetre():
    """Une conversation qui continue ne doit pas se couper en plein milieu."""
    from src.ears.jev_reflexe import FenetreConversation

    f = FenetreConversation(duree_s=30.0)
    f.engager(maintenant=100.0)
    f.engager(maintenant=120.0)                 # deuxieme tour adresse
    assert f.engagee(maintenant=149.0)          # prolongee depuis 120, pas 100
    assert not f.engagee(maintenant=151.0)


def test_fermeture_explicite():
    """Couper le mains libres doit refermer la fenetre immediatement."""
    from src.ears.jev_reflexe import FenetreConversation

    f = FenetreConversation(duree_s=30.0)
    f.engager(maintenant=100.0)
    f.fermer()
    assert not f.engagee(maintenant=101.0)


def test_duree_par_defaut_raisonnable():
    """Assez long pour enchainer, assez court pour ne pas capter la piece."""
    from src.ears.jev_reflexe import FenetreConversation

    assert 15.0 <= FenetreConversation().duree_s <= 45.0
