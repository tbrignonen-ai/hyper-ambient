"""Client hôte Windows : appuyer-pour-parler vers le host-agent du conteneur.

    python3 dev/scripts/serve_hostagent.py
    python native/hostagent/talk.py
"""
from __future__ import annotations

import argparse
import json
import os
import socket
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
NOMS_MICRO_PREFERES: tuple[str, ...] = (
    "USB PnP",
    "USB Desk Microphone",
)
NOM_MICRO_PREFERE: str | tuple[str, ...] = NOMS_MICRO_PREFERES


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


def lister_peripheriques(sd) -> str:
    """Inventaire des micros et des haut-parleurs, sans ouvrir de flux.

    Un périphérique duplex apparaît dans les deux sections : c'est le
    casque USB de la démo, et le cacher du côté sortie reproduirait
    le bug d'aujourd'hui (haut-parleur mort indistinguable d'un micro
    mort).
    """
    peripheriques = sd.query_devices()
    try:
        apis = sd.query_hostapis()
    except Exception:
        apis = []
    entrees: list[str] = []
    sorties: list[str] = []
    for indice, peripherique in enumerate(peripheriques):
        nom = peripherique["name"]
        taux = int(peripherique["default_samplerate"])
        n_in = int(peripherique["max_input_channels"])
        n_out = int(peripherique["max_output_channels"])
        hostapi_idx = peripherique.get("hostapi")
        api_nom = ""
        if (
            apis
            and hostapi_idx is not None
            and isinstance(hostapi_idx, int)
            and hostapi_idx < len(apis)
        ):
            api_nom = f"  [{apis[hostapi_idx]['name']}]"
        if n_in > 0:
            mot = "canal" if n_in == 1 else "canaux"
            entrees.append(f"  [{indice}] {nom}{api_nom} — {n_in} {mot}, {taux} Hz")
        if n_out > 0:
            mot = "canal" if n_out == 1 else "canaux"
            sorties.append(f"  [{indice}] {nom}{api_nom} — {n_out} {mot}, {taux} Hz")
    lignes = ["Entrées :"]
    lignes.extend(entrees or ["  (aucune)"])
    lignes.append("Sorties :")
    lignes.extend(sorties or ["  (aucune)"])
    return "\n".join(lignes)


def decrire_erreur_peripherique(exc: BaseException) -> str:
    """Traduit une exception audio en une phrase : le problème, et quoi taper ensuite."""
    texte = str(exc).lower()
    if "busy" in texte or "in use" in texte:
        return (
            "Le périphérique audio est occupé par une autre application. "
            "Fermez-la, puis lancez --lister pour voir les périphériques disponibles."
        )
    if "invalid sample rate" in texte or "invalid number of channels" in texte:
        return (
            "Le format audio est refusé (taux d'échantillonnage ou nombre de canaux). "
            "Lancez --test-sortie pour vérifier le haut-parleur."
        )
    if "invalid device" in texte or "device unavailable" in texte:
        return (
            "Le périphérique audio est absent, invalide ou introuvable. "
            "Lancez --lister pour voir les périphériques disponibles."
        )
    return (
        "Le périphérique audio a refusé l'ouverture. "
        "Lancez --lister pour voir les périphériques disponibles, "
        "ou --test-sortie pour vérifier le haut-parleur."
    )


def canaux_de_sortie(max_output_channels: int | None) -> int:
    """Détermine le nombre de canaux à ouvrir pour la restitution.

    - 0 ou absent : échec bruyant en français.
    - 1 : périphérique réellement mono.
    - >= 2 : 2 (stéréo nominale, dupliquée).
    """
    if not max_output_channels or max_output_channels <= 0:
        print("Aucun canal de sortie disponible sur ce périphérique.")
        raise SystemExit(1)
    if max_output_channels == 1:
        return 1
    return 2


def etaler(pcm, canaux: int):
    """Duplique le signal mono vers N canaux."""
    import numpy as np

    arr = np.asarray(pcm, dtype=np.float32)
    return np.repeat(arr.reshape(-1, 1), canaux, axis=1)


def tester_sortie(sd, *, indice=None, secondes=0.4, frequence=440.0) -> int:
    """Joue un bip au taux de la démo et rend le nombre d'échantillons écrits.

    16 kHz, pas le défaut du périphérique : on vérifie que la restitution
    du tour vocal passera, pas seulement qu'on entend quelque chose.
    """
    import numpy as np

    try:
        if indice is not None:
            info = sd.query_devices(indice)
        else:
            info = sd.query_devices(kind="output")
    except Exception as exc:
        _echouer_peripherique(exc)

    canaux = canaux_de_sortie(info.get("max_output_channels"))
    nom = info.get("name", "inconnu")
    api_info = ""
    try:
        apis = sd.query_hostapis()
        hostapi_idx = info.get("hostapi")
        if hostapi_idx is not None and hostapi_idx < len(apis):
            api_info = f" [{apis[hostapi_idx]['name']}]"
    except Exception:
        pass
    mot_canaux = "canal" if canaux == 1 else "canaux"
    print(f"sortie : {nom} — {canaux} {mot_canaux} à 16 kHz{api_info}")

    n = int(secondes * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / np.float32(SAMPLE_RATE)
    signal = (
        np.float32(0.2) * np.sin(np.float32(2.0 * np.pi) * np.float32(frequence) * t)
    ).astype(np.float32)
    kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": canaux,
        "dtype": "float32",
    }
    if indice is not None:
        kwargs["device"] = indice
    flux = sd.OutputStream(**kwargs)
    try:
        flux.start()
        flux.write(etaler(signal, canaux))
    finally:
        try:
            flux.stop()
        except Exception:
            pass
        flux.close()
    return n


def _echouer_peripherique(exc: BaseException) -> None:
    """Imprime la phrase utile et sort. Jamais de trace, jamais l'anglais brut."""
    print(decrire_erreur_peripherique(exc))
    raise SystemExit(1)


def _est_erreur_audio(exc: BaseException) -> bool:
    """True si le texte ressemble à PortAudio, pas à un refus de connexion."""
    texte = str(exc).lower()
    return any(
        marqueur in texte
        for marqueur in (
            "invalid device",
            "device unavailable",
            "device or resource busy",
            "in use",
            "invalid sample rate",
            "invalid number of channels",
            "error opening inputstream",
            "error opening outputstream",
            "paerrorcode",
        )
    )


def _resoudre_indice(demande: str, peripheriques, *, canaux: str, role: str) -> int:
    """Indice numérique, ou premier nom qui contient le fragment."""
    try:
        return int(demande)
    except ValueError:
        fragment = demande.lower()
        for indice, peripherique in enumerate(peripheriques):
            if (
                peripherique[canaux] > 0
                and fragment in peripherique["name"].lower()
            ):
                return indice
        print(f"Aucun périphérique {role} ne correspond à {demande!r}.")
        print("Lancez --lister pour voir les périphériques disponibles.")
        raise SystemExit(1)


def resoudre_peripherique_api(nom_api: str, peripheriques: list[dict], hostapis: list[dict], *, role: str = "max_output_channels") -> int:
    """Trouve le premier périphérique du rôle demandé correspondant à l'API spécifiée."""
    nom_api_normalise = nom_api.strip().lower()
    indices_api = [
        i for i, api in enumerate(hostapis)
        if nom_api_normalise in api.get("name", "").lower()
    ]
    if not indices_api:
        print(f"L'API hôte audio {nom_api!r} n'a pas été trouvée sur cette machine.")
        print("Lancez --lister pour voir les APIs et périphériques disponibles.")
        raise SystemExit(1)

    for indice, periph in enumerate(peripheriques):
        if periph.get(role, 0) > 0 and periph.get("hostapi") in indices_api:
            return indice

    role_texte = "de sortie" if role == "max_output_channels" else "d'entrée"
    print(f"Aucun périphérique {role_texte} trouvé pour l'API {nom_api!r}.")
    print("Lancez --lister pour voir les périphériques disponibles.")
    raise SystemExit(1)


def choisir_sortie(demande: str | None, sd, *, api: str | None = None) -> int | None:
    """Résout ``--sortie`` (indice ou fragment de nom) ou ``--api``. None = défaut système."""
    if demande is None and api is None:
        return None
    try:
        peripheriques = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception as exc:
        _echouer_peripherique(exc)

    if demande is not None:
        indice = _resoudre_indice(
            demande, peripheriques, canaux="max_output_channels", role="de sortie"
        )
    else:
        indice = resoudre_peripherique_api(
            api, peripheriques, hostapis, role="max_output_channels"
        )

    nom = sd.query_devices(indice)["name"]
    print(f"Périphérique de sortie : {nom}")
    return indice


def choisir_peripherique(demande: str | None, sd) -> int:
    """Liste les micros et choisit --device, le USB Desk Microphone, ou le défaut."""
    try:
        peripheriques = sd.query_devices()
    except Exception as exc:
        _echouer_peripherique(exc)

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

    candidats = (
        NOM_MICRO_PREFERE
        if isinstance(NOM_MICRO_PREFERE, (list, tuple))
        else (NOM_MICRO_PREFERE,)
    )
    for pref in candidats:
        pref_norm = str(pref).strip().lower()
        if not pref_norm:
            continue
        for indice, peripherique in enumerate(peripheriques):
            if (
                peripherique["max_input_channels"] > 0
                and pref_norm in peripherique["name"].lower()
            ):
                print(f"Périphérique d'entrée : {peripherique['name']}")
                return indice

    try:
        choisi = sd.query_devices(kind="input")
    except Exception as exc:
        _echouer_peripherique(exc)
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
        try:
            return sd.InputStream(
                device=indice,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                callback=callback,
            )
        except Exception as exc:
            _echouer_peripherique(exc)

    return factory


def _ouvrir_sortie(sd, indice: int | None = None):
    """Sortie ouverte une fois : son ouverture ne compte pas dans NFR-01.

    ``indice`` vient de ``--sortie``. None laisse le défaut système.
    """
    try:
        if indice is not None:
            info = sd.query_devices(indice)
        else:
            info = sd.query_devices(kind="output")
    except Exception as exc:
        _echouer_peripherique(exc)

    canaux = canaux_de_sortie(info.get("max_output_channels"))
    nom = info.get("name", "inconnu")
    api_info = ""
    try:
        apis = sd.query_hostapis()
        hostapi_idx = info.get("hostapi")
        if hostapi_idx is not None and hostapi_idx < len(apis):
            api_info = f" [{apis[hostapi_idx]['name']}]"
    except Exception:
        pass
    mot_canaux = "canal" if canaux == 1 else "canaux"
    print(f"sortie : {nom} — {canaux} {mot_canaux} à 16 kHz{api_info}")

    kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": canaux,
        "dtype": "float32",
    }
    if indice is not None:
        kwargs["device"] = indice
    try:
        flux = sd.OutputStream(**kwargs)
    except Exception as exc:
        _echouer_peripherique(exc)
    # Volontairement PAS de `start()` ici. Le flux restait demarre depuis
    # l'ouverture jusqu'au premier mot de MOUTH, soit plusieurs secondes sans
    # une seule ecriture : en mode bloquant, MME et DirectSound font entendre
    # cet underflow comme un souffle continu. On demarre a la premiere trame
    # (voir `_jouer`), ou le buffer est immediatement alimente. Le cout est
    # celui d'un `start()` PortAudio, hors NFR-01 puisqu'il precede l'audible.
    # `channels` n'est pas reecrit ici. sounddevice 0.5.6 l'expose comme une
    # propriete sans setter, et le flux le porte deja : c'est `kwargs` qui l'a
    # pose a l'ouverture. L'assignation, redondante, levait une AttributeError
    # apres un `start()` reussi ; elle tombait dans le meme `except` que les
    # vrais refus materiels et se disait « le peripherique a refuse
    # l'ouverture », puis « verifiez le micro » cote GUI. Le flux restait
    # ouvert et le canal de parole ne s'ouvrait jamais.
    if getattr(flux, "channels", None) != canaux:
        try:
            flux.channels = canaux
        except AttributeError:
            pass
    return flux


def _jouer(sortie, echantillons) -> None:
    canaux = getattr(sortie, "channels", 1)
    pcm = etaler(echantillons, canaux)
    if not pcm.size:
        return
    # Demarrage paresseux : le flux ne tourne que quand il a de quoi jouer.
    if not getattr(sortie, "active", False):
        sortie.start()
    sortie.write(pcm)


def _reposer(sortie) -> None:
    """Arrete le flux entre deux tours, une fois le tampon joue.

    Pendant du demarrage paresseux de `_jouer` : un flux laisse actif dans le
    silence qui suit un enonce recommence a souffler en underflow. `stop()`
    attend que le tampon se vide, donc la fin du dernier mot est preservee.
    """
    try:
        if getattr(sortie, "active", False):
            sortie.stop()
    except Exception as exc:
        # Ne jamais faire tomber le tour pour un flux qu'on voulait juste
        # mettre au repos : le prochain `_jouer` le redemarrera.
        print(f"repos audio : {exc}", flush=True)


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
    print(f"C10 t={time.monotonic():.3f} WS_OPEN", flush=True)
    print("Canal prêt.", flush=True)


def _tour(ws, capture, sortie) -> None:
    input("Entrée pour parler… ")
    capture.start()
    input("Parlez — Entrée pour envoyer… ")
    trames = capture.stop()
    t_fin_parole = time.perf_counter()

    if not trames:
        print(f"C10 t={time.monotonic():.3f} AUDIO_SEND n_trames=0 n_samples=0", flush=True)
        print("Aucune trame capturée (parole trop courte).")
        return

    n_samples = sum(int(trame.samples.size) for trame in trames)
    print(
        f"C10 t={time.monotonic():.3f} AUDIO_SEND "
        f"n_trames={len(trames)} n_samples={n_samples}",
        flush=True,
    )
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
        # Le serveur envoie, dans l'ordre : des paquets audio, puis un rapport,
        # puis un marqueur de fin vide. Sortir dès qu'un message n'a pas de
        # trames revenait à sortir SUR LE RAPPORT, en laissant le marqueur de
        # fin dans la socket — le tour suivant le lisait à la place de sa
        # propre réponse, et annonçait « aucune trame ». Un tour sur deux se
        # décalait. Seul le marqueur vide termine le tour.
        if message.get("type") == "state":
            relayer_etat(message)
            continue
        if message.get("type") == "report":
            entendu = (message.get("transcript") or "").strip()
            repondu = (message.get("reply") or "").strip()
            if entendu:
                print(f"  compris : {entendu}")
            if repondu:
                print(f"  réponse : {repondu}")
            continue
        recues = message.get("frames")
        if recues is None:
            continue
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



# --- Relais vers la presence visuelle ----------------------------------------
#
# La surcouche graphique est un processus separe : on veut pouvoir la fermer, la
# relancer ou ne jamais la lancer sans que la conversation s'en apercoive. Le
# relais se fait donc en datagramme UDP local, et non par une connexion.
#
# Ce choix n'est pas un raccourci, c'est la garantie recherchee : un datagramme
# part sans poignee de main, sans accuse de reception et sans destinataire vivant.
# Il ne peut structurellement pas faire attendre le chemin de parole, ce qui est
# la regle qui commande toute la presence — l'etat ne doit jamais retarder le son.

PORT_PRESENCE = int(os.getenv("PRESENCE_PORT", "8123"))
_douille_presence: socket.socket | None = None


def relayer_etat(message: dict) -> None:
    """Transmet un etat a la presence visuelle, si elle ecoute. Sans jamais bloquer."""
    global _douille_presence
    if os.getenv("PRESENCE", "1") == "0":
        return
    try:
        if _douille_presence is None:
            _douille_presence = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _douille_presence.setblocking(False)
        _douille_presence.sendto(
            json.dumps(message).encode("utf-8"), ("127.0.0.1", PORT_PRESENCE)
        )
    except OSError:
        # Personne n'ecoute, ou la pile reseau refuse : ce n'est pas une erreur.
        # La voix continue, c'est tout ce qui compte.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Appuyer-pour-parler vers le host-agent du conteneur."
    )
    parser.add_argument(
        "--device",
        default=None,
        help="indice PortAudio, ou fragment du nom du micro",
    )
    parser.add_argument(
        "--sortie",
        default=None,
        help="indice PortAudio, ou fragment du nom du haut-parleur",
    )
    parser.add_argument(
        "--lister",
        action="store_true",
        help="lister les périphériques d'entrée et de sortie, puis sortir",
    )
    parser.add_argument(
        "--test-sortie",
        dest="test_sortie",
        action="store_true",
        help="jouer un bip sur le haut-parleur, puis sortir",
    )
    parser.add_argument(
        "--api",
        default=None,
        choices=["wasapi", "mme", "directsound", "wdm-ks"],
        help="API audio hôte opt-in (ex: wasapi, mme)",
    )
    parser.add_argument("--url", default=URL_DEFAUT, help="URL WebSocket du transport")
    args = parser.parse_args()

    sd = _importer_sounddevice()

    if args.lister:
        try:
            print(lister_peripheriques(sd))
        except Exception as exc:
            _echouer_peripherique(exc)
        return

    if args.test_sortie:
        try:
            indice_sortie = choisir_sortie(args.sortie, sd, api=args.api)
            tester_sortie(sd, indice=indice_sortie)
        except SystemExit:
            raise
        except Exception as exc:
            _echouer_peripherique(exc)
        return

    connect = _importer_websockets()
    secret = lire_secret()
    indice = choisir_peripherique(args.device, sd)
    capture = PushToTalkCapture(stream_factory=_fabrique_entree(indice, sd))
    indice_sortie = choisir_sortie(args.sortie, sd, api=args.api)
    sortie = _ouvrir_sortie(sd, indice=indice_sortie)
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
        if _est_erreur_audio(exc):
            print(decrire_erreur_peripherique(exc))
        else:
            print(f"Impossible de joindre {args.url} : {exc}")
            print("Le conteneur écoute-t-il ?  python3 dev/scripts/serve_hostagent.py")
        raise SystemExit(1)
    finally:
        sortie.stop()
        sortie.close()


if __name__ == "__main__":
    main()
