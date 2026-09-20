"""Seuil JeV calibre par la mesure, et court-circuit sur le nom du produit."""
from __future__ import annotations


def test_seuil_par_defaut_est_celui_mesure():
    """0.60 : le plus bas sans faux positif sur 32 phrases mesurees le 2026-09-20.

    A 0.75 (ancien defaut), neuf phrases adressees sur seize etaient ignorees,
    dont « tu m'entends ? » et « dis-moi l'heure ». A 0.55, une phrase de
    television en fond (« et maintenant, place au film de la soiree ») passait
    a 0.55 — un faux declenchement coute plus cher qu'une ignorance.
    """
    from src.ears.jev_reflexe import JevThresholds

    assert JevThresholds().noul_true == 0.60


def test_le_nom_du_produit_suffit_sans_appeler_jev():
    """Dire son nom, c'est s'adresser a elle. Aucun appel distant necessaire.

    Mesure du 2026-09-20 : « Hyper Ambient » prononce seul score 0.39 chez JeV,
    sous tout seuil raisonnable. Le modele distant juge mal les enonces d'un
    seul mot. Or l'intention est ici certaine, et locale a verifier : on tranche
    sans payer d'appel.
    """
    from src.ears.jev_reflexe import nom_du_produit_prononce as nom

    assert nom("Hyper Ambient")
    assert nom("hyper ambiant, tu es la ?")
    assert nom("eh, HYPER-AMBIENT !")
    assert nom("MOTHER, annule")
    assert nom("dis hyper ambient")

    assert not nom("bon alors on disait le module deux")
    assert not nom("il etait une fois une petite fille")
    assert not nom("")
    # Piege : un mot qui contient le nom sans etre le nom.
    assert not nom("cette ambiance est hyper agreable")


def test_nom_tolere_ce_que_whisper_entend_vraiment():
    """Whisper deforme le nom : il faut reconnaitre ses deformations reelles.

    Mesures en conditions reelles le 2026-09-20, micro USB, segments courts :
      « Hyper ambient »              -> « l'ambiance »
      « Hyper ambiant, tu m'entends » -> « Super ambiante, est-ce que tu l'entends ? »

    Ajouter le nom a EARS_HOTWORDS n'a pas suffi. Plutot que d'exiger une
    transcription parfaite, on accepte la famille de formes que le moteur rend
    : prefixe hyper/super/hypere, et ambient/ambiant/ambiance/ambiante.
    """
    from src.ears.jev_reflexe import nom_du_produit_prononce as nom

    assert nom("Super ambiante, est-ce que tu l'entends ?")
    assert nom("hyper ambiance")
    assert nom("Hyper Ambient")
    assert nom("hyper ambiant")
    assert nom("MOTHER")

    # Ne doit pas se declencher sur un usage ordinaire de ces mots.
    assert not nom("cette ambiance est agreable")
    assert not nom("c'est super")
    assert not nom("il fait super beau dans cette piece")
