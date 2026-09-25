"""L'emission de l'etat vers la presence visuelle.

La regle qui commande tout : l'etat ne doit JAMAIS retarder la premiere trame
audio. C'est la meme discipline que le rapport de fin de tour, mais plus stricte,
parce que l'etat s'emet AU MILIEU du tour et non a la fin — un envoi qui bloque
sur une socket lente decalerait la voix, ce qui est exactement le defaut qu'on
cherche a eviter dans une conversation parlee.

D'ou le contrat teste ici : `emettre` rend la main immediatement, quoi que fasse
la socket. Elle ne l'attend pas, et une socket en panne ne remonte jamais dans le
chemin de parole.
"""
import asyncio

import pytest

from src.presence.etat import ETATS, Presence, EtatInconnu


class _SocketLente:
    """Une socket qui n'aboutit jamais : le pire cas pour le chemin audio."""

    def __init__(self) -> None:
        self.tentatives = 0

    async def send_json(self, message: dict) -> None:
        self.tentatives += 1
        await asyncio.Event().wait()


class _SocketFactice:
    def __init__(self) -> None:
        self.envois: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.envois.append(message)


class _SocketCassee:
    async def send_json(self, message: dict) -> None:
        raise ConnectionResetError("le client est parti")


@pytest.mark.asyncio
async def test_emettre_rend_la_main_sans_attendre_la_socket():
    presence = Presence(_SocketLente())

    debut = asyncio.get_running_loop().time()
    presence.emettre("ecoute")
    ecoule = asyncio.get_running_loop().time() - debut

    assert ecoule < 0.01, "emettre a attendu la socket : le son serait en retard"


@pytest.mark.asyncio
async def test_l_etat_finit_par_arriver():
    socket = _SocketFactice()
    presence = Presence(socket)

    presence.emettre("parole")
    await presence.vider()

    assert socket.envois == [{"type": "state", "etat": "parole"}]


@pytest.mark.asyncio
async def test_le_meme_etat_deux_fois_n_est_envoye_qu_une_fois():
    socket = _SocketFactice()
    presence = Presence(socket)

    presence.emettre("reflexion")
    presence.emettre("reflexion")
    await presence.vider()

    assert len(socket.envois) == 1


@pytest.mark.asyncio
async def test_les_etats_arrivent_dans_l_ordre_emis():
    socket = _SocketFactice()
    presence = Presence(socket)

    for etat in ("ecoute", "reflexion", "escalade", "parole", "repos"):
        presence.emettre(etat)
    await presence.vider()

    assert [envoi["etat"] for envoi in socket.envois] == [
        "ecoute", "reflexion", "escalade", "parole", "repos"
    ]


@pytest.mark.asyncio
async def test_une_socket_cassee_ne_remonte_pas_dans_le_chemin_de_parole():
    presence = Presence(_SocketCassee())

    presence.emettre("parole")
    await presence.vider()  # ne doit pas lever


@pytest.mark.asyncio
async def test_le_niveau_sonore_accompagne_l_ecoute():
    socket = _SocketFactice()
    presence = Presence(socket)

    presence.emettre("ecoute", niveau=0.42)
    await presence.vider()

    assert socket.envois[0]["niveau"] == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_le_niveau_est_borne_entre_zero_et_un():
    socket = _SocketFactice()
    presence = Presence(socket)

    presence.emettre("ecoute", niveau=3.7)
    presence.emettre("repos")
    presence.emettre("ecoute", niveau=-2.0)
    await presence.vider()

    assert socket.envois[0]["niveau"] == 1.0
    assert socket.envois[2]["niveau"] == 0.0


@pytest.mark.asyncio
async def test_un_etat_inconnu_est_refuse_a_l_emission():
    presence = Presence(_SocketFactice())

    with pytest.raises(EtatInconnu):
        presence.emettre("perplexe")


@pytest.mark.asyncio
async def test_sans_socket_l_emission_ne_fait_rien():
    presence = Presence(None)

    presence.emettre("parole")
    await presence.vider()


def test_les_cinq_etats_du_cahier_des_charges_existent():
    # 25/09 : sixième état, l'appel à un harnais (Codex, Claude).
    assert ETATS == ("repos", "ecoute", "reflexion", "escalade", "harnais", "parole")
