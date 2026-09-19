"""Nombres arabes → lettres FR, sûrs sur fragments streamés.

Magpie saute « 24 » et « 12 ». On verbalise avant synthèse : heures,
dates, rues, entiers, décimaux, pourcentages. Un chiffre collé en fin
de fragment ne se convertit pas — le fragment suivant peut encore
l'allonger.
"""
from src.mouth.normalize import nombres_en_lettres


def test_heure_quinze_heures_trente():
    assert nombres_en_lettres("à 15h30") == "à quinze heures trente"


def test_heure_une_heure_trente():
    assert nombres_en_lettres("à 1h30,") == "à une heure trente,"


def test_date_et_numero_de_rue():
    texte = nombres_en_lettres("jeudi 24 septembre, au 12 rue des Lilas.")
    assert "vingt-quatre" in texte
    assert "douze" in texte
    assert "24" not in texte
    assert "12" not in texte


def test_entier_decimal_pourcentage():
    assert nombres_en_lettres("7 pommes.") == "sept pommes."
    assert nombres_en_lettres("3,14 litres.") == "trois virgule quatorze litres."
    assert nombres_en_lettres("50% déjà.") == "cinquante pour cent déjà."


def test_fragment_chiffre_final_non_consomme():
    assert nombres_en_lettres("jeudi 2") == "jeudi 2"
    assert nombres_en_lettres("jeudi 24 septembre") == "jeudi vingt-quatre septembre"


def test_phrase_c9():
    src = "Rendez-vous jeudi 24 septembre à 15h30, au 12 rue des Lilas."
    out = nombres_en_lettres(src)
    assert out == (
        "Rendez-vous jeudi vingt-quatre septembre à quinze heures trente, "
        "au douze rue des Lilas."
    )
