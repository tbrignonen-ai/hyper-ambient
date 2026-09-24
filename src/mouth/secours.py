"""
Parole de repli : un silence est indistinguable d'une panne pour
quelqu'un qui écoute.

Les quatre cas dégradés — micro muet, énoncé trop long, BRAIN
injoignable, modèle muet — sont ce qui casse une démonstration en
direct. Jamais la fonctionnalité principale : le tour réussi tient
déjà, et une phrase de secours qui se déclenche à tort le ruinerait.

Cette décision est pure. Le harnais appelle, MOUTH prononce.
"""
from __future__ import annotations

LIMITE_ENONCE_S = 30.0

# fr / en / es. Le tu, pas le vous : c'est la voix du produit
# (« Je suis là. Prends ton temps, je t'écoute. »).
_PHRASES: dict[str, dict[str, str]] = {
    "fr": {
        "silence": "Je n'ai rien entendu. Reprends, je suis là.",
        "micro_muet": "Je n'entends plus rien, vérifie qu'aucune autre application n'utilise ton micro.",
        "trop_long": "C'était un peu long. Plus court, je t'écoute.",
        "injoignable": "Je n'arrive pas à réfléchir. Reprends dans un instant.",
        "muet": "Je n'ai rien à dire. Reprends, je t'écoute.",
    },
    "en": {
        "silence": "I didn't hear anything. I'm here, take your time.",
        "micro_muet": "I can't hear anything, check that no other app is using your microphone.",
        "trop_long": "That ran a little long. Shorter, and I'm listening.",
        "injoignable": "I can't quite think right now. Try again in a moment.",
        "muet": "I have nothing to say. I'm here when you're ready.",
    },
    "es": {
        "silence": "No he oído nada. Tómate tu tiempo, estoy aquí.",
        "micro_muet": "Ya no oigo nada, comprueba que ninguna otra aplicación use tu micrófono.",
        "trop_long": "Ha sido un poco largo. Dilo más corto, te escucho.",
        "injoignable": "No consigo pensar ahora. Vuelve a intentarlo en un momento.",
        "muet": "No tengo nada que decir. Cuando quieras, estoy aquí.",
    },
}


def phrase_de_secours(
    *,
    transcript: str,
    # Ces trois-la restent OBLIGATOIRES a dessein. Leur donner une valeur par
    # defaut rendrait un appel incomplet silencieusement valide : un appelant
    # qui oublie `reply` obtiendrait `reply=""`, donc la phrase « Je n'ai rien
    # a dire » prononcee a tort. C'est exactement l'accident que ce module
    # existe pour empecher — voir l'avertissement en tete de fichier.
    reply: str,
    brain_injoignable: bool,
    duree_audio_s: float,
    langue: str = "fr",
    mains_libres: bool = False,
    micro_muet: bool = False,
) -> str | None:
    """Rend la phrase à prononcer quand le tour a mal tourné, ou None si tout va bien.

    ``mains_libres`` change une seule chose : en écoute continue, un segment
    sans parole ne dit rien. L'utilisateur n'a rien demandé — le micro est
    ouvert en permanence, et annoncer le silence ferait parler en boucle. En
    appuyer-pour-parler il a appuyé, donc il attend une réaction : la phrase
    reste. Les autres causes s'annoncent dans les deux modes, parce qu'elles
    suivent toujours une vraie demande.
    """
    voix = _PHRASES.get(langue, _PHRASES["fr"])

    # La durée l'emporte sur le silence, qui l'emporte sur BRAIN.
    # La durée est un FAIT connu indépendamment de la transcription,
    # alors qu'un transcript vide est AMBIGU — il peut venir d'un micro
    # muet comme d'une transcription qu'on a volontairement sautée.
    # On annonce la cause qu'on connaît avec certitude.
    if duree_audio_s > LIMITE_ENONCE_S:
        return voix["trop_long"]
    if not transcript.strip():
        if mains_libres:
            return None
        return voix["micro_muet"] if micro_muet else voix["silence"]
    if brain_injoignable:
        return voix["injoignable"]
    if not reply.strip():
        return voix["muet"]
    return None

# Seuil d'energie en dessous duquel on considere qu'il n'y a pas eu de parole.
# -50 dBFS en valeur efficace : un micro ouvert dans une piece calme reste
# nettement en dessous, une voix meme lointaine passe nettement au dessus.
SEUIL_SILENCE_RMS = 10 ** (-50.0 / 20.0)


def est_silence(audio, seuil: float = SEUIL_SILENCE_RMS) -> bool:
    """Vrai si le signal ne porte pas de parole, mesure sur son energie.

    On ne deduit pas le silence du transcript. Mesure faite sur ce serveur :
    2 secondes de silence numerique ont donne « Sous-titrage ST' 501 » --
    Whisper recrache des credits de sous-titrage vus a l'entrainement quand on
    lui donne du vide. Le transcript n'etant pas vide, la phrase de secours ne
    partait pas et BRAIN repetait l'hallucination a voix haute.

    L'energie, elle, est un fait : elle ne depend d'aucun modele.
    """
    import numpy as np

    tableau = np.asarray(audio, dtype=np.float32).ravel()
    if tableau.size == 0:
        return True
    return bool(float(np.sqrt(np.mean(np.square(tableau)))) < seuil)


def est_micro_muet(audio) -> bool:
    """Vrai si le signal n'est fait que de zeros numeriques exacts.

    C'est la signature d'un micro coupe dans Windows ou tenu par une autre
    application : le pilote livre des trames nulles. Une piece silencieuse
    n'en donne jamais, le souffle du preampli suffit a decoller du zero.
    """
    import numpy as np

    tableau = np.asarray(audio, dtype=np.float32).ravel()
    return bool(tableau.size == 0 or not np.any(tableau))
