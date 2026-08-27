"""
Ce qui casse une démonstration n'est jamais la boucle qui marche.

Le tour réussi tient déjà 928 ms. Quand quelque chose se passe mal —
micro muet, énoncé trop long, BRAIN injoignable, modèle qui rend du
vide — le serveur fait aujourd'hui `return` sans rien dire. Devant une
équipe, ce silence est indistinguable d'une panne : on ne sait pas si
l'assistant réfléchit, s'il n'a pas entendu, ou s'il est mort.

Ces tests figent la parole de repli. Elle n'a rien à faire dans le
harnais `serve_hostagent` : c'est une décision de produit, pure, sans
socket ni sommeil. Le cas le plus important n'est pas la panne, c'est
le tour réussi : une phrase de secours qui se déclenche à tort ruine
chaque échange. Les autres cas existent pour qu'on diagnostique à
l'oreille, en démo, quel étage a lâché — et pour que l'usager entende
une phrase humaine, jamais un message de log.
"""
from __future__ import annotations

import inspect

# L'import vit dans les tests, pas au chargement du fichier : sinon
# pytest s'arrête à la collecte et n'atteint jamais les autres fichiers
# de la phase rouge. Le module n'existe pas encore ; chaque test échoue
# à l'import, c'est le contrat.

# Termes d'atelier : les entendre dans le haut-parleur trahirait que
# l'excuse est un log, pas une phrase. Comparaison insensible à la
# casse — « Erreur » ou « EARS » sont tout aussi techniques.
_TERMES_TECHNIQUES = ("ears", "transcript", "none", "erreur", "exception")


def _limite() -> float:
    from src.mouth.secours import LIMITE_ENONCE_S

    return LIMITE_ENONCE_S


def _secours(**kwargs) -> str | None:
    """Tour français raisonnable, sauf ce que le test surcharge."""
    from src.mouth.secours import phrase_de_secours

    valeurs = {
        "transcript": "bonjour",
        "reply": "je vous écoute",
        "brain_injoignable": False,
        "duree_audio_s": 2.0,
        "langue": "fr",
    }
    valeurs.update(kwargs)
    return phrase_de_secours(**valeurs)


def _est_phrase_humaine(phrase: str | None) -> str:
    """Une excuse de démo : non vide, brève, sans jargon d'atelier."""
    assert phrase is not None, "une panne doit se dire, pas se taire"
    assert phrase.strip(), "une phrase blanche est un silence déguisé"
    assert len(phrase) < 140, (
        "on n'entend pas un discours : au-delà de 140 caractères, "
        "le secours devient plus long que l'échec qu'il explique"
    )
    texte = phrase.lower()
    for terme in _TERMES_TECHNIQUES:
        assert terme not in texte, (
            f"« {terme} » est un mot d'atelier : l'usager n'a pas à "
            f"l'entendre ({phrase!r})"
        )
    return phrase


def test_un_tour_reussi_ne_prononce_rien():
    """Rien en plus. C'est le cas à protéger en premier.

    Une phrase de secours qui se déclenche à tort s'ajouterait à chaque
    réponse réussie. En démo, ça ruinerait le tour, pas la panne.
    """
    assert (
        _secours(
            transcript="bonjour",
            reply="bonjour, je vous écoute",
            brain_injoignable=False,
            duree_audio_s=2.0,
        )
        is None
    )
    assert _limite() == 30.0


def test_un_silence_dit_qu_on_n_a_rien_entendu():
    """Micro muet ou blanc : on le dit, sans jargon, sans discours."""
    for transcript in ("", "   ", "\t\n"):
        _est_phrase_humaine(_secours(transcript=transcript))


def test_un_enonce_a_la_limite_est_encore_accepte():
    """Frontière inclusive : pile LIMITE_ENONCE_S, ce n'est pas trop long."""
    assert _secours(duree_audio_s=_limite()) is None


def test_un_enonce_au_dela_de_la_limite_invite_a_reformuler():
    """Au-delà, on n'enchaîne pas : on demande plus court."""
    phrase = _est_phrase_humaine(
        _secours(duree_audio_s=_limite() + 0.01)
    )
    assert phrase != _secours(transcript="")


def test_brain_injoignable_n_est_pas_la_phrase_du_silence():
    """Deux pannes, deux excuses. Sinon on diagnostique faux à l'oreille."""
    silence = _est_phrase_humaine(_secours(transcript=""))
    injoignable = _est_phrase_humaine(_secours(brain_injoignable=True))
    assert injoignable != silence


def test_brain_joignable_mais_muet_produit_une_phrase_distincte():
    """BRAIN a répondu le vide : ce n'est ni un silence, ni une coupure."""
    silence = _est_phrase_humaine(_secours(transcript=""))
    injoignable = _est_phrase_humaine(_secours(brain_injoignable=True))
    muet = _est_phrase_humaine(
        _secours(reply="", brain_injoignable=False)
    )
    assert muet != silence
    assert muet != injoignable


def test_le_silence_l_emporte_sur_les_pannes_en_aval():
    """Transcript vide ET BRAIN injoignable → c'est la phrase du silence.

    BRAIN n'a rien à dire si on n'a rien entendu. Un « je n'arrive pas
    à réfléchir » alors que le micro était muet ferait chercher le bug
    du mauvais côté pendant la démo.
    """
    silence = _secours(transcript="")
    combine = _secours(transcript="", brain_injoignable=True)
    assert combine == silence


def test_la_duree_l_emporte_sur_le_silence_et_brain():
    """Durée > silence > BRAIN.

    La durée est un fait connu indépendamment de la transcription ;
    un transcript vide est ambigu — micro muet, ou transcription
    volontairement sautée. On annonce la cause qu'on connaît
    avec certitude : sinon, sauter EARS au-delà de 30 s ferait
    entendre « je n'ai rien entendu » alors que le problème est
    la longueur.
    """
    trop_long = _secours(duree_audio_s=_limite() + 1.0)
    avec_silence = _secours(
        transcript="",
        duree_audio_s=_limite() + 1.0,
    )
    avec_brain = _secours(
        duree_audio_s=_limite() + 1.0,
        brain_injoignable=True,
    )
    les_trois = _secours(
        transcript="",
        duree_audio_s=_limite() + 1.0,
        brain_injoignable=True,
    )
    assert avec_silence == trop_long
    assert avec_brain == trop_long
    assert les_trois == trop_long
    assert trop_long != _secours(transcript="")
    assert trop_long != _secours(brain_injoignable=True)


def test_reply_vide_et_injoignable_c_est_la_coupure():
    """Reply vide ET BRAIN injoignable → c'est la panne de transport.

    Une coupure se diagnostique autrement qu'un modèle muet : on
    cherche le réseau, pas le prompt.
    """
    injoignable = _secours(brain_injoignable=True)
    combine = _secours(reply="", brain_injoignable=True)
    muet = _secours(reply="", brain_injoignable=False)
    assert combine == injoignable
    assert combine != muet


def test_les_trois_langues_rendent_des_phrases_distinctes():
    """fr, en, es : trois chaînes différentes, même panne. Pas la traduction mot à mot."""
    cas = (
        {"transcript": ""},
        {"duree_audio_s": _limite() + 1.0},
        {"brain_injoignable": True},
        {"reply": ""},
    )
    for kwargs in cas:
        phrases = [
            _secours(**kwargs, langue=langue) for langue in ("fr", "en", "es")
        ]
        assert all(phrases), f"chaque langue doit parler ({kwargs})"
        assert len(set(phrases)) == 3, (
            "les trois langues doivent s'entendre distinctement, "
            f"même cas {kwargs} : {phrases!r}"
        )


def test_une_langue_inconnue_retombe_sur_le_francais():
    """Pas d'exception : un code hors fr/en/es parle français."""
    francais = _secours(transcript="", langue="fr")
    inconnu = _secours(transcript="", langue="zz")
    assert inconnu == francais


def test_le_module_est_une_fonction_de_decision_pure():
    """Pas de sommeil, pas de socket, pas de journal : elle décide, elle se tait."""
    import src.mouth.secours as secours

    source = inspect.getsource(secours)
    assert "import asyncio" not in source
    assert "websocket" not in source
    assert "print(" not in source


# --- Le silence ne se reconnait pas au transcript ---------------------------
#
# Mesure sur le serveur reel, 2 secondes de silence numerique envoyees dans la
# boucle complete : EARS a rendu « Sous-titrage ST' 501 ». C'est une
# hallucination connue de Whisper, qui recrache des credits de sous-titrage vus
# a l'entrainement quand on lui donne du vide. Le transcript n'etant pas vide,
# la phrase de secours du silence ne se declenchait pas, et BRAIN repetait
# l'hallucination a voix haute.
#
# On ne peut donc pas DEDUIRE le silence de la transcription. On le MESURE sur
# le signal, avant de transcrire -- meme raisonnement que pour la duree : un
# fait mesurable l'emporte sur une sortie de modele ambigue.


def test_un_signal_muet_est_reconnu_comme_silence():
    from src.mouth.secours import est_silence
    import numpy as np

    assert est_silence(np.zeros(16000, dtype=np.float32)) is True


def test_de_la_parole_n_est_pas_prise_pour_du_silence():
    from src.mouth.secours import est_silence
    import numpy as np

    t = np.linspace(0.0, 1.0, 16000, endpoint=False, dtype=np.float32)
    parole = (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    assert est_silence(parole) is False


def test_un_souffle_de_micro_reste_du_silence():
    from src.mouth.secours import est_silence
    import numpy as np

    # Bruit de fond a -60 dBFS : un micro ouvert dans une piece calme. C'est
    # exactement ce qui faisait halluciner Whisper, donc ca doit compter comme
    # du silence, pas comme un enonce.
    souffle = (np.random.RandomState(0).randn(16000) * 0.001).astype(np.float32)
    assert est_silence(souffle) is True


def test_un_signal_vide_est_du_silence():
    from src.mouth.secours import est_silence
    import numpy as np

    assert est_silence(np.zeros(0, dtype=np.float32)) is True
