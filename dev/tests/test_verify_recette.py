"""La recette doit savoir reconnaitre la fin d'un tour, et elle ne le savait pas.

Panne mesuree le 13 septembre, et elle a coute une demi-journee de diagnostic a
l'envers. `verify_hostagent_loop.py` rendait « ECHEC — aucune trame de reponse »
sur une chaine vocale **saine** : la sonde `_probe_client.py`, branchee sur le
meme serveur au meme moment, recevait 197 messages dont 194 paquets audio, avec
transcription juste et reponse pertinente, en 8,28 s.

La cause tient en une ligne de la recette :

    recues = message.get("frames") or []
    if not recues:
        break

Le serveur emet desormais, sur le meme socket, des messages de presence
`{"type": "state", ...}` et un `{"type": "report", ...}` — aucun des deux ne
porte de cle `frames`. Or le **premier** message d'un tour est un `state`, a
0,01 s, avant tout audio. La recette sortait donc de sa boucle sur le premier
message recu, systematiquement, et concluait a l'absence de voix.

`talk.py` porte deja un commentaire sur ce piege exact et l'a corrige ; la
recette, elle, etait restee en arriere — d'ou son dernier artefact reussi date
du 29 aout. La lecon epinglee ici : **seul un `invoke` audio a trames vides
termine un tour.** Un message de presence ou un rapport se traverse, il ne
conclut rien. Un instrument de mesure faux est pire que pas d'instrument : il
fait chercher la panne dans le produit.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _recette():
    """Import tardif : le module tire numpy et l'audio d'hote au chargement."""
    import importlib

    return importlib.import_module("dev.scripts.verify_hostagent_loop")


def test_un_message_de_presence_ne_termine_pas_le_tour():
    """Le cas exact de la panne : `state` arrive en premier, a 0,01 s."""
    recette = _recette()
    assert recette.est_fin_de_tour({"type": "state", "etat": "ecoute"}) is False


def test_un_rapport_ne_termine_pas_le_tour():
    """Le rapport arrive APRES l'audio mais AVANT le marqueur de fin."""
    recette = _recette()
    message = {
        "type": "report",
        "transcript": "bonjour",
        "reply": "bonjour a vous",
        "amorces": "",
        "timings_ms": {},
    }
    assert recette.est_fin_de_tour(message) is False


def test_un_paquet_audio_ne_termine_pas_le_tour():
    recette = _recette()
    message = {
        "type": "invoke",
        "primitive": "audio.render",
        "frames": [[0.0] * 320],
    }
    assert recette.est_fin_de_tour(message) is False


def test_seul_un_invoke_a_trames_vides_termine_le_tour():
    recette = _recette()
    message = {"type": "invoke", "primitive": "audio.render", "frames": []}
    assert recette.est_fin_de_tour(message) is True


def test_un_message_qui_n_est_pas_un_dictionnaire_ne_termine_rien():
    recette = _recette()
    assert recette.est_fin_de_tour(["frames"]) is False
    assert recette.est_fin_de_tour(None) is False


def test_les_trames_audio_ne_sont_lues_que_sur_un_invoke():
    """Un `state` ou un `report` ne doit jamais etre compte comme de l'audio."""
    recette = _recette()
    assert recette.trames_audio({"type": "state", "etat": "parole"}) == []
    assert recette.trames_audio({"type": "report", "reply": "bonjour"}) == []
    assert recette.trames_audio({"type": "invoke", "frames": []}) == []
    paquet = {"type": "invoke", "primitive": "audio.render", "frames": [[0.5] * 320]}
    assert recette.trames_audio(paquet) == [[0.5] * 320]


def test_un_tour_complet_se_lit_sans_sortir_trop_tot():
    """Le scenario mesure, dans l'ordre reel : state, audio, state, report, fin.

    C'est le test qui aurait evite la demi-journee perdue : il rejoue la
    sequence exacte observee et verifie qu'on collecte bien l'audio avant de
    s'arreter, au lieu de sortir sur le premier message sans trames.
    """
    recette = _recette()
    sequence = [
        {"type": "state", "etat": "ecoute"},
        {"type": "invoke", "primitive": "audio.render", "frames": [[0.1] * 320]},
        {"type": "state", "etat": "parole"},
        {"type": "invoke", "primitive": "audio.render", "frames": [[0.2] * 320]},
        {"type": "report", "transcript": "bonjour", "reply": "bonjour a vous"},
        {"type": "invoke", "primitive": "audio.render", "frames": []},
    ]

    collectees = []
    lus = 0
    for message in sequence:
        lus += 1
        if recette.est_fin_de_tour(message):
            break
        collectees.extend(recette.trames_audio(message))

    assert lus == 6, "la boucle est sortie avant le marqueur de fin"
    assert len(collectees) == 2, "l'audio du tour n'a pas ete collecte en entier"
