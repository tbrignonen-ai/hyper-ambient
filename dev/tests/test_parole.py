"""La forme comparée d'un énoncé est unique."""
from src.parole import normaliser


def test_accents_casse_et_ponctuation():
    assert normaliser("  Été,  l'heure ! ") == "ete l heure"
    assert normaliser("") == ""
    assert normaliser(None) == ""  # type: ignore[arg-type]
