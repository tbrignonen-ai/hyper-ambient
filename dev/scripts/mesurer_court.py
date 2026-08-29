"""Les echantillons Supertonic d'une nuit precedente avaient ete produits avec la
phrase courte. Les mesurer contre la phrase longue faisait apparaitre 55,6 %
d'erreur, qui n'etait qu'un desaccord de reference et non un defaut de la voix.
"""
import asyncio

import dev.scripts.banc_piper as banc
import dev.scripts.mesurer_wav as mesure

COURTE = "Bonjour, je suis la. Prends ton temps, je t ecoute."
banc.PHRASE = COURTE
mesure.PHRASE = COURTE

if __name__ == "__main__":
    asyncio.run(mesure.main("supertonic_*_fr.wav"))
