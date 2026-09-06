"""
Vague J — presence visuelle, nappe hote (sans pytest-asyncio).

`test_presence.py` marque les tests `@pytest.mark.asyncio`. Sur l'hote le
plugin est absent : ces tests ne se collectent pas. Ici le meme contrat
critique (l'etat ne retarde jamais l'audio) tourne via asyncio.run, plus
les bords que le fichier d'origine ne pince pas :

  - emettre n'est pas une coroutine
  - un meme etat avec niveau (VU) n'est PAS deduplique
  - niveau=0.0 est emis (0.0 n'est pas None)
  - socket morte → websocket=None, les emissions suivantes restent hors chemin critique
  - OSError / TimeoutError avales
  - etats sensibles a la casse

asyncio.run — pas de pytest-asyncio. Pas de carte son, pas de socket reelle.
"""
from __future__ import annotations

import asyncio
import functools
import inspect

import pytest

from src.presence.etat import ETATS, EtatInconnu, Presence


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class _SocketFactice:
    def __init__(self):
        self.envois = []

    async def send_json(self, message: dict) -> None:
        self.envois.append(message)


class _SocketQuiLeve:
    def __init__(self, exc):
        self.exc = exc
        self.tentatives = 0

    async def send_json(self, message: dict) -> None:
        self.tentatives += 1
        raise self.exc


class _SocketLente:
    def __init__(self):
        self.tentatives = 0

    async def send_json(self, message: dict) -> None:
        self.tentatives += 1
        await asyncio.Event().wait()


def test_emettre_n_est_pas_une_coroutine():
    assert not inspect.iscoroutinefunction(Presence.emettre)
    assert inspect.iscoroutinefunction(Presence.vider)


def test_cinq_etats_dans_l_ordre_du_cahier():
    assert ETATS == ("repos", "ecoute", "reflexion", "escalade", "parole")


@runs_async
async def test_emettre_ne_touche_pas_la_socket_avant_vider():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute")
    assert socket.envois == []
    await presence.vider()
    assert socket.envois == [{"type": "state", "etat": "ecoute"}]


@runs_async
async def test_emettre_rend_la_main_meme_si_la_socket_est_lente():
    socket = _SocketLente()
    presence = Presence(socket)
    debut = asyncio.get_running_loop().time()
    presence.emettre("parole")
    ecoule = asyncio.get_running_loop().time() - debut
    assert ecoule < 0.01
    assert socket.tentatives == 0, "send_json ne doit partir qu'au vider"


@runs_async
async def test_meme_etat_sans_niveau_n_est_envoye_qu_une_fois():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("reflexion")
    presence.emettre("reflexion")
    presence.emettre("reflexion")
    await presence.vider()
    assert socket.envois == [{"type": "state", "etat": "reflexion"}]


@runs_async
async def test_meme_etat_avec_niveau_n_est_pas_deduplique():
    """Le VU d'ecoute doit pouvoir bouger sans changer d'etat."""
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute", niveau=0.2)
    presence.emettre("ecoute", niveau=0.8)
    await presence.vider()
    assert [e["niveau"] for e in socket.envois] == [pytest.approx(0.2), pytest.approx(0.8)]
    assert all(e["etat"] == "ecoute" for e in socket.envois)


@runs_async
async def test_niveau_zero_est_emis_pas_traite_comme_absent():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute", niveau=0.0)
    await presence.vider()
    assert "niveau" in socket.envois[0]
    assert socket.envois[0]["niveau"] == 0.0


@runs_async
async def test_apres_vu_le_meme_etat_sans_niveau_est_deduplique():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute", niveau=0.5)
    presence.emettre("ecoute")
    await presence.vider()
    assert len(socket.envois) == 1
    assert socket.envois[0]["niveau"] == pytest.approx(0.5)


@runs_async
async def test_sans_niveau_puis_avec_niveau_les_deux_partent():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute")
    presence.emettre("ecoute", niveau=0.3)
    await presence.vider()
    assert len(socket.envois) == 2
    assert "niveau" not in socket.envois[0]
    assert socket.envois[1]["niveau"] == pytest.approx(0.3)


@runs_async
async def test_ordre_des_cinq_etats():
    socket = _SocketFactice()
    presence = Presence(socket)
    for etat in ETATS:
        presence.emettre(etat)
    await presence.vider()
    assert [e["etat"] for e in socket.envois] == list(ETATS)


@runs_async
async def test_niveau_borne_zero_un():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute", niveau=4)
    presence.emettre("repos")
    presence.emettre("ecoute", niveau=-1)
    await presence.vider()
    assert socket.envois[0]["niveau"] == 1.0
    assert socket.envois[2]["niveau"] == 0.0


@runs_async
async def test_niveau_entier_un_devient_float():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute", niveau=1)
    await presence.vider()
    assert socket.envois[0]["niveau"] == 1.0
    assert isinstance(socket.envois[0]["niveau"], float)


@pytest.mark.parametrize("exc", [
    ConnectionResetError("parti"),
    OSError("reseau"),
    TimeoutError("lent"),
    RuntimeError("ws down"),
])
@runs_async
async def test_exceptions_socket_n_explosent_pas_vider(exc):
    presence = Presence(_SocketQuiLeve(exc))
    presence.emettre("parole")
    await presence.vider()
    presence.emettre("repos")
    await presence.vider()  # websocket deja None


@runs_async
async def test_apres_panne_plus_aucun_send():
    socket = _SocketQuiLeve(ConnectionResetError("x"))
    presence = Presence(socket)
    presence.emettre("parole")
    await presence.vider()
    assert socket.tentatives == 1
    assert presence._websocket is None
    presence.emettre("repos")
    await presence.vider()
    assert socket.tentatives == 1


@runs_async
async def test_sans_socket_ne_leve_pas():
    presence = Presence(None)
    presence.emettre("parole")
    presence.emettre("ecoute", niveau=0.1)
    await presence.vider()
    await presence.vider()


@runs_async
async def test_vider_file_vide_est_un_noop():
    presence = Presence(_SocketFactice())
    await presence.vider()
    await presence.vider()


@pytest.mark.parametrize("etat", ["", "Ecoute", "PAROLE", "perplexe", "idle", " "])
def test_etat_hors_liste_leve_a_l_emission(etat):
    presence = Presence(_SocketFactice())
    with pytest.raises(EtatInconnu):
        presence.emettre(etat)


def test_etat_inconnu_est_un_valueerror():
    assert issubclass(EtatInconnu, ValueError)
    presence = Presence(_SocketFactice())
    with pytest.raises(EtatInconnu, match="perplexe"):
        presence.emettre("perplexe")


@runs_async
async def test_emission_invalide_n_empoisonne_pas_la_file():
    socket = _SocketFactice()
    presence = Presence(socket)
    presence.emettre("ecoute")
    with pytest.raises(EtatInconnu):
        presence.emettre("???")
    presence.emettre("parole")
    await presence.vider()
    assert [e["etat"] for e in socket.envois] == ["ecoute", "parole"]
