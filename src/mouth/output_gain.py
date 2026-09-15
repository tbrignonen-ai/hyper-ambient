"""Gain final de MOUTH, juste avant la restitution par le client Windows."""
from __future__ import annotations

import numpy as np


def appliquer_gain_doux(echantillons, gain_db: float) -> np.ndarray:
    """Applique un gain en dB et borne doucement le signal dans [-1, 1].

    La pente autour de zero reste celle du gain lineaire demande. Aux forts
    niveaux, ``tanh`` remplace l'ecretage dur par une transition progressive.
    """
    x = np.asarray(echantillons, dtype=np.float32)
    if x.size == 0 or gain_db == 0.0:
        return np.ascontiguousarray(x)

    gain = np.float32(10.0 ** (gain_db / 20.0))
    if gain < 1.0:
        return np.ascontiguousarray(x * gain, dtype=np.float32)

    # La normalisation conserve exactement +/-1 a pleine echelle. Pour les
    # signaux de parole ordinaires, la pente vaut pratiquement ``gain``.
    plafond = np.tanh(gain)
    return np.ascontiguousarray(np.tanh(x * gain) / plafond, dtype=np.float32)
