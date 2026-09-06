"""_ouvrir_sortie face a un OutputStream dont ``channels`` est en lecture seule.

Regression du 2026-09-03 : sounddevice 0.5.6 expose ``OutputStream.channels``
comme une propriete sans setter. ``_ouvrir_sortie`` faisait
``flux.channels = canaux`` apres un ``start()`` reussi ; l'AttributeError
tombait dans le ``except Exception`` du meme bloc et ressortait en
« Le peripherique audio a refuse l'ouverture », puis, cote GUI, en
« Verifiez le micro ». Le peripherique n'avait rien refuse du tout, et le
canal WebSocket n'etait jamais ouvert.

Les doubles des autres nappes posent ``self.channels = 2`` en attribut
ordinaire, donc assignable : ils ne pouvaient pas voir la regression. Ici le
double reproduit la vraie contrainte.
"""
from __future__ import annotations

import numpy as np
import pytest

import native.hostagent.talk as talk


class _FluxChannelsVerrouille:
    """OutputStream a la sounddevice 0.5.6 : ``channels`` sans setter."""

    def __init__(self, canaux):
        self._canaux = canaux
        self.demarre = False

    @property
    def channels(self):
        return self._canaux

    def start(self):
        self.demarre = True

    def write(self, data):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class _SoundDeviceVerrouille:
    def __init__(self, info):
        self._info = info
        self.appels_output = []

    def query_devices(self, indice=None, kind=None):
        return self._info

    def query_hostapis(self):
        return [{"name": "MME"}]

    def OutputStream(self, **kwargs):
        self.appels_output.append(kwargs)
        return _FluxChannelsVerrouille(kwargs["channels"])


INFO_SURROUND = {
    "name": "Haut-parleurs (Sound Blaster Z)",
    "max_output_channels": 6,
    "hostapi": 0,
}


def test_ouvrir_sortie_accepte_un_flux_dont_channels_est_en_lecture_seule():
    """Un `channels` non assignable ne doit pas etre pris pour un refus materiel."""
    sd = _SoundDeviceVerrouille(INFO_SURROUND)
    flux = talk._ouvrir_sortie(sd, indice=None)
    assert flux.demarre is True
    assert flux.channels == 2


def test_jouer_etale_bien_sur_un_flux_channels_en_lecture_seule():
    """La restitution lit `channels` sur le flux : 2 canaux, pas le fallback mono."""
    sd = _SoundDeviceVerrouille(INFO_SURROUND)
    flux = talk._ouvrir_sortie(sd, indice=None)
    ecrits = []
    flux.write = lambda bloc: ecrits.append(np.asarray(bloc))
    talk._jouer(flux, np.array([0.5, -0.5], dtype=np.float32))
    assert ecrits[0].shape == (2, 2)
