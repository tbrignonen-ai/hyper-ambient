"""Hauteur reelle de l'enregistrement de reference.

Une autocorrelation sur un extrait entier melange les silences, les respirations
et l'eventuelle musique de fond : elle rend un chiffre qui ne decrit aucune voix.
On decoupe donc en fenetres, on ne garde que celles qui portent assez d'energie
et dont l'autocorrelation est franche, et on prend la mediane.
"""
import wave

import numpy as np

CHEMIN = "/workspace/data/voix/ref_aurora_24k.wav"
FENETRE_S = 0.05


def main() -> None:
    with wave.open(CHEMIN, "rb") as w:
        taux = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0

    n = int(taux * FENETRE_S)
    lo, hi = int(taux / 400), int(taux / 60)
    seuil = np.sqrt(np.mean(x ** 2)) * 0.5

    hauteurs = []
    for debut in range(0, len(x) - n, n):
        bloc = x[debut : debut + n]
        if np.sqrt(np.mean(bloc ** 2)) < seuil:
            continue
        bloc = bloc - bloc.mean()
        ac = np.correlate(bloc, bloc, "full")[n - 1:]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        pic = lo + int(np.argmax(ac[lo:hi]))
        if ac[pic] < 0.35:  # autocorrelation molle : fenetre non voisee
            continue
        hauteurs.append(taux / pic)

    h = np.array(hauteurs)
    print(f"fenetres voisees retenues : {len(h)} sur {len(x) // n}")
    print(f"f0 mediane : {np.median(h):.1f} Hz")
    print(f"quartiles  : {np.percentile(h, 25):.1f} – {np.percentile(h, 75):.1f} Hz")


if __name__ == "__main__":
    main()
