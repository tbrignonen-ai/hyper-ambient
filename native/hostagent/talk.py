"""Client hôte Windows : appuyer-pour-parler vers le host-agent du conteneur.

    python3 dev/scripts/serve_hostagent.py
    python native/hostagent/talk.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from native.hostagent.windows_audio import PushToTalkCapture
from src.hostagent.audio import SAMPLE_RATE

# Adresse en IPv4 explicite, jamais « localhost ». Sous Windows, localhost se
# resout vers ::1 en premier, et avec networkingMode=mirrored dans .wslconfig la
# boucle locale IPv6 n'atteint pas le conteneur : la poignee de main WebSocket
# s'ouvre puis expire sans que rien n'arrive cote serveur. Mesure du 2026-08-26 :
# 127.0.0.1 repond, ::1 et localhost expirent tous les deux.
URL_DEFAUT = "ws://127.0.0.1:8001/hostagent"
SECRET_DEVELOPPEMENT = "partage-installation"
NOM_MICRO_PREFERE = "USB Desk Microphone"


def lire_secret() -> str:
    """Secret d'installation, ou valeur de développement si la variable manque."""
    secret = os.environ.get("MOTHER_HOSTAGENT_SECRET")
    if secret:
        return secret
    print(
        "ATTENTION : MOTHER_HOSTAGENT_SECRET est absent. "
        "Secret de développement utilisé (« partage-installation »). "
        "Ne pas exposer ce service hors de la machine.",
        file=sys.stderr,
        flush=True,
    )
    return SECRET_DEVELOPPEMENT


def _importer_sounddevice():
    """Import paresseux : ce module ne doit pas planter dans le conteneur."""
    try:
        import sounddevice as sd
    except ImportError:
        print(
            "sounddevice est absent : ce programme capture et restitue l'audio "
            "de l'hôte Windows et ne peut pas s'exécuter là où le paquet "
            "n'est pas installé (conteneur, CI)."
        )
        raise SystemExit(1)
    return sd


def _importer_websockets():
    """websockets est déjà dans le conteneur ; sur l'hôte il peut manquer."""
    try:
        from websockets.sync.client import connect
    except ImportError:
        print(
            "websockets est absent sur l'hôte. Installez-le avec : "
            "pip install websockets "
            "(déjà présent dans le conteneur, voir requirements.txt)."
        )
        raise SystemExit(1)
    return connect


def choisir_peripherique(demande: str | None, sd) -> int:
    """Liste les micros et choisit --device, le USB Desk Microphone, ou le défaut."""
    try:
        peripheriques = sd.query_devices()
    except Exception as exc:
        print(f"Impossible d'interroger les périphériques audio : {exc}")
        raise SystemExit(1)

    print("Périphériques d'entrée disponibles :")
    for indice, peripherique in enumerate(peripheriques):
        if peripherique["max_input_channels"] > 0:
            print(f"  [{indice}] {peripherique['name']}")

    if demande is not None:
        try:
            indice = int(demande)
        except ValueError:
            indice = None
            fragment = demande.lower()
            for i, peripherique in enumerate(peripheriques):
                if (
                    peripherique["max_input_channels"] > 0
                    and fragment in peripherique["name"].lower()
                ):
                    indice = i
                    break
            if indice is None:
                print(f"Aucun périphérique d'entrée ne correspond à {demande!r}.")
                raise SystemExit(1)
        nom = sd.query_devices(indice)["name"]
        print(f"Périphérique d'entrée : {nom}")
        return indice

    for indice, peripherique in enumerate(peripheriques):
        if (
            peripherique["max_input_channels"] > 0
            and NOM_MICRO_PREFERE in peripherique["name"]
        ):
            print(f"Périphérique d'entrée : {peripherique['name']}")
            return indice

    try:
        choisi = sd.query_devices(kind="input")
    except Exception as exc:
        print(f"Impossible d'interroger les périphériques audio : {exc}")
        raise SystemExit(1)
    print(f"Périphérique d'entrée : {choisi['name']} (défaut système)")
    for indice, peripherique in enumerate(peripheriques):
        if (
            peripherique["name"] == choisi["name"]
            and peripherique["max_input_channels"] > 0
        ):
            return indice
    return int(sd.default.device[0])


def _fabrique_entree(indice: int, sd):
    """Fabrique de flux injectée dans PushToTalkCapture, micro choisi inclus."""

    def factory(callback):
        return sd.InputStream(
            device=indice,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=callback,
        )

    return factory


def _ouvrir_sortie(sd):
    """Sortie par défaut, ouverte une fois : son ouverture ne compte pas dans NFR-01."""
    flux = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    flux.start()
    return flux


def _jouer(sortie, echantillons) -> None:
    import numpy as np

    pcm = np.asarray(echantillons, dtype=np.float32).reshape(-1, 1)
    if pcm.size:
        sortie.write(pcm)


def _poignee_de_main(ws, secret: str) -> None:
    ws.send(json.dumps({"type": "hello", "secret": secret}))
    brut = ws.recv()
    try:
        reponse = json.loads(brut)
    except json.JSONDecodeError:
        print(f"Poignée de main illisible : {brut!r}")
        raise SystemExit(1)
    if reponse.get("type") != "ready":
        print(f"Poignée de main refusée : {reponse}")
        raise SystemExit(1)
    print("Canal prêt.", flush=True)


def _tour(ws, capture, sortie) -> None:
    input("Entrée pour parler… ")
    capture.start()
    input("Parlez — Entrée pour envoyer… ")
    trames = capture.stop()
    t_fin_parole = time.perf_counter()

    if not trames:
        print("Aucune trame capturée (parole trop courte).")
        return

    ws.send(
        json.dumps(
            {
                "type": "invoke",
                "primitive": "audio.capture",
                "frames": [trame.samples.tolist() for trame in trames],
            }
        )
    )
    print(f"{len(trames)} trames envoyées, attente de la réponse…", flush=True)

    premier_son = None
    while True:
        brut = ws.recv()
        try:
            message = json.loads(brut)
        except json.JSONDecodeError:
            print(f"Message illisible : {brut!r}")
            return
        if message.get("type") == "error":
            print(f"Erreur du transport : {message}")
            return
        recues = message.get("frames") or []
        if not recues:
            break
        a_jouer = []
        for brute in recues:
            a_jouer.extend(brute)
        if premier_son is None:
            premier_son = time.perf_counter()
            audible_ms = (premier_son - t_fin_parole) * 1000
            print(
                f"mic_to_audible : {audible_ms:.0f} ms  (fin de parole → premier son)",
                flush=True,
            )
        _jouer(sortie, a_jouer)

    if premier_son is None:
        print("Aucune trame de réponse — rien à restituer.")
    else:
        time.sleep(0.25)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Appuyer-pour-parler vers le host-agent du conteneur."
    )
    parser.add_argument(
        "--device",
        default=None,
        help="indice PortAudio, ou fragment du nom du micro",
    )
    parser.add_argument("--url", default=URL_DEFAUT, help="URL WebSocket du transport")
    args = parser.parse_args()

    sd = _importer_sounddevice()
    connect = _importer_websockets()
    secret = lire_secret()
    indice = choisir_peripherique(args.device, sd)
    capture = PushToTalkCapture(stream_factory=_fabrique_entree(indice, sd))

    sortie = _ouvrir_sortie(sd)
    try:
        with connect(args.url, max_size=16 * 1024 * 1024) as ws:
            _poignee_de_main(ws, secret)
            print(
                "Boucle appuyer-pour-parler. Ctrl+C pour quitter.",
                flush=True,
            )
            while True:
                _tour(ws, capture, sortie)
    except KeyboardInterrupt:
        print("\nArrêt.")
    except Exception as exc:
        print(f"Impossible de joindre {args.url} : {exc}")
        print("Le conteneur écoute-t-il ?  python3 dev/scripts/serve_hostagent.py")
        raise SystemExit(1)
    finally:
        sortie.stop()
        sortie.close()


if __name__ == "__main__":
    main()
