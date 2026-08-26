"""Vérification de recette du pont audio, sans micro ni intervention.

    python dev/scripts/verify_hostagent_loop.py

Reprend exactement le protocole WebSocket de native/hostagent/talk.py :
poignée hello/ready, invoke audio.capture (listes de flottants), attente
des invoke audio.render jusqu'au marqueur vide de fin de tour.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from native.hostagent.windows_audio import frames_from_samples
from src.hostagent.audio import SAMPLE_RATE

# Adresse en IPv4 explicite, jamais « localhost ». Sous Windows, localhost se
# resout vers ::1 en premier, et avec networkingMode=mirrored dans .wslconfig la
# boucle locale IPv6 n'atteint pas le conteneur : la poignee de main WebSocket
# s'ouvre puis expire sans que rien n'arrive cote serveur. Mesure du 2026-08-26 :
# 127.0.0.1 repond, ::1 et localhost expirent tous les deux.
URL_DEFAUT = "ws://127.0.0.1:8001/hostagent"
SECRET_DEVELOPPEMENT = "partage-installation"
QUESTION_DEFAUT = _ROOT / "data" / "in" / "question.wav"
SORTIE_DEFAUT = _ROOT / "data" / "out" / "verify_loop_reponse.wav"
BUDGET_NFR01_MS = 1200
TIMEOUT_REPONSE_S = 60.0
TIMEOUT_POIGNEE_S = 10.0


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


def _importer_soundfile():
    try:
        import soundfile as sf
    except ImportError:
        print(
            "soundfile est absent sur l'hôte. Installez-le avec : "
            "pip install soundfile numpy"
        )
        raise SystemExit(1)
    return sf


def _vers_mono(pcm: np.ndarray) -> np.ndarray:
    arr = np.asarray(pcm, dtype=np.float32)
    if arr.ndim == 1:
        return np.ascontiguousarray(arr)
    return np.ascontiguousarray(arr.mean(axis=1), dtype=np.float32)


def _reechantillonner(pcm: np.ndarray, orig_sr: int, cible: int) -> np.ndarray:
    """Ramène le PCM à 16 kHz par interpolation linéaire (numpy, pas librosa)."""
    pcm = _vers_mono(pcm)
    if orig_sr == cible or pcm.size == 0:
        return pcm
    n_cible = int(round(pcm.size * cible / orig_sr))
    if n_cible <= 0:
        return np.zeros(0, dtype=np.float32)
    t_orig = np.arange(pcm.size, dtype=np.float64) / float(orig_sr)
    t_cible = np.arange(n_cible, dtype=np.float64) / float(cible)
    return np.interp(t_cible, t_orig, pcm).astype(np.float32)


def _charger_question(chemin: Path, sf) -> np.ndarray:
    if not chemin.is_file():
        print(f"Fichier introuvable : {chemin}")
        print("Placez un WAV dans data/in/question.wav.")
        raise SystemExit(1)
    try:
        pcm, orig_sr = sf.read(str(chemin), dtype="float32", always_2d=True)
    except Exception as exc:
        print(f"Impossible de lire {chemin} : {exc}")
        raise SystemExit(1)
    return _reechantillonner(pcm, int(orig_sr), SAMPLE_RATE)


def _poignee_de_main(ws, secret: str) -> None:
    ws.send(json.dumps({"type": "hello", "secret": secret}))
    try:
        brut = ws.recv(timeout=TIMEOUT_POIGNEE_S)
    except TimeoutError:
        print(
            "Poignée de main : le serveur n'a pas répondu « ready » "
            f"en {TIMEOUT_POIGNEE_S:.0f} s."
        )
        raise SystemExit(1)
    try:
        reponse = json.loads(brut)
    except json.JSONDecodeError:
        print(f"Poignée de main illisible : {brut!r}")
        raise SystemExit(1)
    if not isinstance(reponse, dict) or reponse.get("type") != "ready":
        print(f"Poignée de main refusée : {reponse}")
        raise SystemExit(1)
    print("Canal prêt.", flush=True)


def _texte_optionnel(message: dict, cles: tuple[str, ...]) -> str | None:
    for cle in cles:
        valeur = message.get(cle)
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()
    return None


def _rapport(
    *,
    duree_envoyee_s: float | None,
    n_envoyees: int,
    n_recues: int,
    mic_to_audible_ms: float | None,
    duree_recue_s: float | None,
    transcript: str | None,
    reponse_modele: str | None,
    sortie: Path | None,
    verdict: str,
    raison: str,
) -> None:
    def _duree(valeur: float | None) -> str:
        return "—" if valeur is None else f"{valeur:.2f} s"

    if mic_to_audible_ms is None:
        ligne_latence = "—"
    else:
        marge = "≤" if mic_to_audible_ms <= BUDGET_NFR01_MS else ">"
        ligne_latence = (
            f"{mic_to_audible_ms:.0f} ms  "
            f"(budget NFR-01 : {BUDGET_NFR01_MS} ms, {marge} budget)"
        )

    print()
    print("=== Rapport de recette du pont audio ===")
    print(f"  durée audio envoyé     : {_duree(duree_envoyee_s)}")
    print(f"  trames envoyées        : {n_envoyees}")
    print(f"  trames reçues          : {n_recues}")
    print(f"  mic_to_audible         : {ligne_latence}")
    print(f"  durée audio reçu       : {_duree(duree_recue_s)}")
    print(
        "  texte transcrit        : "
        + (transcript if transcript else "(non fourni par le serveur)")
    )
    print(
        "  réponse du modèle      : "
        + (reponse_modele if reponse_modele else "(non fournie par le serveur)")
    )
    if sortie is not None:
        print(f"  fichier écrit          : {sortie}")
    print(f"VERDICT : {verdict} — {raison}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recette du pont audio host-agent, sans micro."
    )
    parser.add_argument("--url", default=URL_DEFAUT, help="URL WebSocket du transport")
    parser.add_argument(
        "--audio",
        default=str(QUESTION_DEFAUT),
        help="WAV d'entrée (défaut : data/in/question.wav)",
    )
    parser.add_argument(
        "--out",
        default=str(SORTIE_DEFAUT),
        help="WAV de sortie (défaut : data/out/verify_loop_reponse.wav)",
    )
    args = parser.parse_args()

    sf = _importer_soundfile()
    connect = _importer_websockets()
    secret = lire_secret()

    pcm = _charger_question(Path(args.audio), sf)
    trames = frames_from_samples(pcm)
    n_envoyees = len(trames)
    duree_envoyee_s = pcm.size / SAMPLE_RATE if pcm.size else 0.0

    if not trames:
        _rapport(
            duree_envoyee_s=duree_envoyee_s,
            n_envoyees=0,
            n_recues=0,
            mic_to_audible_ms=None,
            duree_recue_s=None,
            transcript=None,
            reponse_modele=None,
            sortie=None,
            verdict="ECHEC",
            raison="aucune trame à envoyer (fichier trop court)",
        )
        raise SystemExit(1)

    echantillons_recus: list[float] = []
    n_recues = 0
    mic_to_audible_ms: float | None = None
    transcript: str | None = None
    reponse_modele: str | None = None
    t_fin_envoi: float | None = None

    try:
        with connect(args.url, max_size=16 * 1024 * 1024) as ws:
            _poignee_de_main(ws, secret)
            ws.send(
                json.dumps(
                    {
                        "type": "invoke",
                        "primitive": "audio.capture",
                        "frames": [trame.samples.tolist() for trame in trames],
                    }
                )
            )
            # talk.py n'envoie pas de second marqueur : l'invoke ci-dessus
            # est le message de fin de tour (toutes les trames d'un coup).
            t_fin_envoi = time.perf_counter()
            print(
                f"{n_envoyees} trames envoyées, attente de la réponse…",
                flush=True,
            )

            while True:
                restant = TIMEOUT_REPONSE_S - (time.perf_counter() - t_fin_envoi)
                if restant <= 0:
                    raise TimeoutError("reponse")
                try:
                    brut = ws.recv(timeout=restant)
                except TimeoutError as exc:
                    raise TimeoutError("reponse") from exc
                try:
                    message = json.loads(brut)
                except json.JSONDecodeError:
                    _rapport(
                        duree_envoyee_s=duree_envoyee_s,
                        n_envoyees=n_envoyees,
                        n_recues=n_recues,
                        mic_to_audible_ms=mic_to_audible_ms,
                        duree_recue_s=None,
                        transcript=transcript,
                        reponse_modele=reponse_modele,
                        sortie=None,
                        verdict="ECHEC",
                        raison=f"message illisible : {brut!r}",
                    )
                    raise SystemExit(1)
                if not isinstance(message, dict):
                    _rapport(
                        duree_envoyee_s=duree_envoyee_s,
                        n_envoyees=n_envoyees,
                        n_recues=n_recues,
                        mic_to_audible_ms=mic_to_audible_ms,
                        duree_recue_s=None,
                        transcript=transcript,
                        reponse_modele=reponse_modele,
                        sortie=None,
                        verdict="ECHEC",
                        raison=f"message inattendu : {message!r}",
                    )
                    raise SystemExit(1)
                if message.get("type") == "error":
                    _rapport(
                        duree_envoyee_s=duree_envoyee_s,
                        n_envoyees=n_envoyees,
                        n_recues=n_recues,
                        mic_to_audible_ms=mic_to_audible_ms,
                        duree_recue_s=None,
                        transcript=transcript,
                        reponse_modele=reponse_modele,
                        sortie=None,
                        verdict="ECHEC",
                        raison=f"erreur du transport : {message}",
                    )
                    raise SystemExit(1)

                if transcript is None:
                    transcript = _texte_optionnel(
                        message, ("transcript", "transcription", "prompt")
                    )
                if reponse_modele is None:
                    reponse_modele = _texte_optionnel(
                        message, ("response", "reply", "answer", "text")
                    )
                    if reponse_modele and transcript and reponse_modele == transcript:
                        reponse_modele = None

                recues = message.get("frames") or []
                if not recues:
                    break
                if mic_to_audible_ms is None:
                    mic_to_audible_ms = (
                        time.perf_counter() - t_fin_envoi
                    ) * 1000
                    print(
                        f"mic_to_audible : {mic_to_audible_ms:.0f} ms  "
                        "(fin d'envoi → première trame)",
                        flush=True,
                    )
                n_recues += len(recues)
                for brute in recues:
                    echantillons_recus.extend(brute)
    except SystemExit:
        raise
    except TimeoutError:
        if echantillons_recus:
            print(
                f"Délai de {TIMEOUT_REPONSE_S:.0f} s atteint : "
                "fin de tour absente, mais de l'audio a déjà été reçu.",
                flush=True,
            )
        else:
            _rapport(
                duree_envoyee_s=duree_envoyee_s,
                n_envoyees=n_envoyees,
                n_recues=0,
                mic_to_audible_ms=None,
                duree_recue_s=None,
                transcript=transcript,
                reponse_modele=reponse_modele,
                sortie=None,
                verdict="ECHEC",
                raison=(
                    f"aucune réponse audio en {TIMEOUT_REPONSE_S:.0f} s "
                    "(le serveur est-il lancé ? les modèles sont-ils chargés ?)"
                ),
            )
            raise SystemExit(1)
    except OSError as exc:
        print(f"Impossible de joindre {args.url} : {exc}")
        print("Le conteneur écoute-t-il ?  python3 dev/scripts/serve_hostagent.py")
        _rapport(
            duree_envoyee_s=duree_envoyee_s,
            n_envoyees=n_envoyees,
            n_recues=0,
            mic_to_audible_ms=None,
            duree_recue_s=None,
            transcript=None,
            reponse_modele=None,
            sortie=None,
            verdict="ECHEC",
            raison=f"impossible de joindre {args.url}",
        )
        raise SystemExit(1)
    except Exception as exc:
        print(f"Impossible de joindre {args.url} : {exc}")
        print("Le conteneur écoute-t-il ?  python3 dev/scripts/serve_hostagent.py")
        _rapport(
            duree_envoyee_s=duree_envoyee_s,
            n_envoyees=n_envoyees,
            n_recues=n_recues,
            mic_to_audible_ms=mic_to_audible_ms,
            duree_recue_s=None,
            transcript=transcript,
            reponse_modele=reponse_modele,
            sortie=None,
            verdict="ECHEC",
            raison=f"connexion interrompue : {exc}",
        )
        raise SystemExit(1)

    if not echantillons_recus:
        _rapport(
            duree_envoyee_s=duree_envoyee_s,
            n_envoyees=n_envoyees,
            n_recues=0,
            mic_to_audible_ms=None,
            duree_recue_s=None,
            transcript=transcript,
            reponse_modele=reponse_modele,
            sortie=None,
            verdict="ECHEC",
            raison="aucune trame de réponse — rien à écrire",
        )
        raise SystemExit(1)

    pcm_out = np.asarray(echantillons_recus, dtype=np.float32)
    duree_recue_s = pcm_out.size / SAMPLE_RATE
    sortie = Path(args.out)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(sortie), pcm_out, SAMPLE_RATE)

    if mic_to_audible_ms is not None and mic_to_audible_ms > BUDGET_NFR01_MS:
        raison = (
            f"audio reçu, mais NFR-01 dépassé "
            f"({mic_to_audible_ms:.0f} ms > {BUDGET_NFR01_MS} ms)"
        )
    else:
        raison = "la boucle a produit de l'audio"

    _rapport(
        duree_envoyee_s=duree_envoyee_s,
        n_envoyees=n_envoyees,
        n_recues=n_recues,
        mic_to_audible_ms=mic_to_audible_ms,
        duree_recue_s=duree_recue_s,
        transcript=transcript,
        reponse_modele=reponse_modele,
        sortie=sortie,
        verdict="OK",
        raison=raison,
    )
    raise SystemExit(0)


if __name__ == "__main__":
    main()
