"""Verification independante du chiffre qui decide : le TTFA de Supertonic.

Le rapport delegue annonce environ 1,4 s avant le premier echantillon, faute
d'API de diffusion. Comme ce seul nombre arbitre entre Supertonic et Piper — 39 ms
sur siwis descendue de six demi-tons — on le remesure ici plutot que de le
reprendre. Trois passes apres chauffe, pour ne pas conclure sur un releve isole.
"""
from __future__ import annotations

import statistics
import sys
import time

import numpy as np

sys.path.insert(0, "/workspace/dev/scripts")

PHRASE = (
    "Bonjour, je suis là. Prends ton temps, je t'écoute. "
    "Le facteur temps réel doit rester inférieur à un."
)
VOIX = "F5"

# Piper tient son TTFA en decoupant la premiere clause. Supertonic n'a pas d'API
# de diffusion, mais rien n'empeche de lui donner la meme premiere bouchee : si
# son facteur temps reel de 0,20 tient, une clause courte doit sortir en ~200 ms.
CLAUSES = ["Bonjour.", "Bonjour, je suis là.", "Bonjour, je suis là. Prends ton temps."]


def main() -> None:
    from banc_supertonic import MODELE, installer_poids
    from supertonic import TTS

    installer_poids()
    tts = TTS(model="supertonic-3", model_dir=str(MODELE), auto_download=False)
    nom = VOIX if VOIX in tts.voice_style_names else tts.voice_style_names[-1]
    style = tts.get_voice_style(nom)

    tts.synthesize("Ok.", voice_style=style, lang="fr")  # chauffe

    for texte in CLAUSES + [PHRASE]:
        releves = []
        for _ in range(3):
            t0 = time.perf_counter()
            wav, _ = tts.synthesize(texte, voice_style=style, lang="fr")
            releves.append((time.perf_counter() - t0) * 1000)
        duree = len(np.asarray(wav).ravel()) / tts.sample_rate
        print(
            f"{len(texte):3d} car. -> {statistics.median(releves):6.0f} ms "
            f"pour {duree:5.2f}s d audio  (facteur temps reel "
            f"{statistics.median(releves) / 1000 / duree:.2f})  {texte[:40]}",
            flush=True,
        )


if __name__ == "__main__":
    main()
