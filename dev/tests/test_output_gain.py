import numpy as np

from src.mouth.output_gain import appliquer_gain_doux


def test_gain_nul_est_transparent():
    entree = np.array([-1.0, -0.25, 0.0, 0.25, 1.0], dtype=np.float32)
    np.testing.assert_array_equal(appliquer_gain_doux(entree, 0.0), entree)


def test_plus_neuf_db_amplifie_la_parole_sans_depasser_pleine_echelle():
    entree = np.linspace(-0.1, 0.1, 2001, dtype=np.float32)
    sortie = appliquer_gain_doux(entree, 9.0)
    gain_rms_db = 20.0 * np.log10(
        np.sqrt(np.mean(sortie**2)) / np.sqrt(np.mean(entree**2))
    )

    assert 8.5 < gain_rms_db < 9.5
    assert np.max(np.abs(sortie)) <= 1.0


def test_limiteur_doux_ne_produit_pas_de_plateau_ecrete():
    entree = np.linspace(-1.0, 1.0, 2001, dtype=np.float32)
    sortie = appliquer_gain_doux(entree, 9.0)

    assert np.all(np.diff(sortie) > 0.0)
    assert sortie[0] >= -1.0
    assert sortie[-1] <= 1.0
