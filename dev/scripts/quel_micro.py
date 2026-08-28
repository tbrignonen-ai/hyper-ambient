"""Quel periphérique porte réellement la voix ?

Windows énumère des dizaines d'entrées, dont la plupart sont des bouclages
(« Mixage stéréo », « What U Hear », « Digital-In ») : elles enregistrent ce que
la machine joue, pas ce qu'on dit. Choisir le défaut système revient souvent à
choisir l'une d'elles, et la chaîne vocale ne reçoit alors que du silence.

Ce script tranche par la mesure : il ouvre chaque entrée plausible à tour de
rôle, écoute deux secondes, et rend le niveau efficace en dBFS. Il suffit de
parler pendant qu'il tourne. Le seuil de la chaîne est à -50 dBFS.
"""
from __future__ import annotations

import sys

import numpy as np
import sounddevice as sd

DUREE_S = 2.0
TAUX = 16000
SEUIL_DBFS = -50.0
BOUCLAGES = ("mixage", "what u hear", "digital-in", "mappeur", "stereo mix", "streaming")


def dbfs(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return 20.0 * np.log10(max(rms, 1e-9))


def candidats() -> list[tuple[int, str]]:
    apis = sd.query_hostapis()
    trouves = []
    for indice, appareil in enumerate(sd.query_devices()):
        if appareil["max_input_channels"] <= 0:
            continue
        nom = appareil["name"]
        if any(mot in nom.lower() for mot in BOUCLAGES):
            continue
        trouves.append((indice, f"{nom}  [{apis[appareil['hostapi']]['name']}]"))
    return trouves


def main() -> None:
    liste = candidats()
    if len(sys.argv) > 1:
        vise = int(sys.argv[1])
        liste = [(i, n) for i, n in liste if i == vise] or [(vise, "(imposé)")]

    print(f"PARLEZ MAINTENANT, en continu. {DUREE_S:.0f} s par périphérique.\n")
    resultats = []
    for indice, nom in liste:
        try:
            enr = sd.rec(
                int(DUREE_S * TAUX), samplerate=TAUX, channels=1,
                dtype="float32", device=indice,
            )
            sd.wait()
            niveau = dbfs(enr.ravel())
            verdict = "VOIX" if niveau > SEUIL_DBFS else "silence"
            print(f"  [{indice:2}] {niveau:7.1f} dBFS  {verdict:8} {nom}")
            resultats.append((niveau, indice, nom))
        except Exception as exc:
            court = str(exc).split("\n")[0][:60]
            print(f"  [{indice:2}]      —   inutilisable  {nom}  ({court})")

    if not resultats:
        print("\nAucune entrée n'a pu être ouverte.")
        return
    resultats.sort(reverse=True)
    niveau, indice, nom = resultats[0]
    print(f"\nMEILLEUR : indice {indice} à {niveau:.1f} dBFS — {nom}")
    if niveau <= SEUIL_DBFS:
        print("Aucun n'atteint le seuil : le micro est muet, coupé, ou désactivé dans Windows.")
    else:
        print(f'\n  python native/hostagent/talk.py --device {indice}')


if __name__ == "__main__":
    main()
