"""Le filtre post-ASR des crédits fantômes de Whisper, et du bruit non vocal."""
from src.ears.silence import (
    est_artefact_whisper_silencieux,
    est_hallucination_whisper,
    jeter_tour_bruit,
    segment_sans_parole,
)


def test_credit_whisper_sur_silence_est_rejete_malgre_apostrophe_et_accents():
    assert est_artefact_whisper_silencieux("Sous-titrage ST' 501") is True
    assert est_artefact_whisper_silencieux("Sous titrage ST 501") is True


def test_une_phrase_reelle_ne_ressemble_pas_au_credit_whisper():
    assert est_artefact_whisper_silencieux("Le sous-titrage de ce film est bon") is False


def test_hallucinations_connues_sont_rejetees():
    """Filet textuel, insensible à la casse et aux accents."""
    assert est_hallucination_whisper("Sous-titrage FR ?") is True
    assert est_hallucination_whisper("Sous-titrage ST' 501") is True
    assert est_hallucination_whisper("Sous-titres réalisés par la communauté d'Amara.org") is True
    assert est_hallucination_whisper("Merci d'avoir regardé cette vidéo") is True
    assert est_hallucination_whisper("Abonnez-vous") is True
    assert est_hallucination_whisper("Subtitles by the community") is True
    assert est_hallucination_whisper("Thanks for watching") is True


def test_une_phrase_normale_passe_le_filet():
    assert est_hallucination_whisper("Bonjour, comment vas-tu ?") is False
    assert est_hallucination_whisper("Je t'écoute") is False


def test_segment_a_forte_probabilite_de_non_parole_est_rejete():
    assert segment_sans_parole({"no_speech_prob": 0.92, "avg_logprob": -0.2}) is True
    assert segment_sans_parole({"no_speech_prob": 0.1, "avg_logprob": -1.8}) is True
    assert segment_sans_parole({"no_speech_prob": 0.1, "avg_logprob": -0.2}) is False


def test_rejet_uniquement_en_mains_libres():
    texte = "Sous-titrage FR ?"
    segments = [{"no_speech_prob": 0.95, "avg_logprob": -2.0}]
    assert jeter_tour_bruit(texte, segments, mains_libres=True) is True
    assert jeter_tour_bruit(texte, segments, mains_libres=False) is False
    assert jeter_tour_bruit("Bonjour.", None, mains_libres=True) is False


def test_une_pause_dans_une_longue_phrase_ne_jette_pas_toute_la_phrase():
    """Séance du 23 sept : phrase de 10 s bien transcrite, un segment de
    pause au no_speech_prob élevé, et tout le tour partait comme bruit."""
    segments = [
        {"no_speech_prob": 0.05, "avg_logprob": -0.2},
        {"no_speech_prob": 0.72, "avg_logprob": -0.4},
        {"no_speech_prob": 0.08, "avg_logprob": -0.3},
    ]
    texte = "Fais un test, envoie-lui par exemple. Bonjour Codex, comment vas-tu ?"
    assert jeter_tour_bruit(texte, segments, mains_libres=True) is False


def test_tous_les_segments_sans_parole_restent_du_bruit():
    segments = [
        {"no_speech_prob": 0.9, "avg_logprob": -0.4},
        {"no_speech_prob": 0.2, "avg_logprob": -1.6},
    ]
    assert jeter_tour_bruit("Merci.", segments, mains_libres=True) is True


def test_phrase_reelle_incertaine_n_est_pas_du_bruit():
    """Séance du 24 sept : « J'ai fait un test à ma lèvre, tu m'entends ? »
    (« mains libres » mal entendu) jeté comme bruit en mains libres. Whisper
    doutait des mots, pas de la parole : une vraie phrase n'est pas jetée sur
    la seule incertitude du décodage. Un bruit court le reste."""
    segments = [{"no_speech_prob": 0.1, "avg_logprob": -1.3}]
    texte = "J'ai fait un test à ma lèvre, tu m'entends ?"
    assert jeter_tour_bruit(texte, segments, mains_libres=True) is False
    assert jeter_tour_bruit("Merci.", segments, mains_libres=True) is True
    # La probabilité de non-parole, elle, reste décisive.
    silence = [{"no_speech_prob": 0.9, "avg_logprob": -1.3}]
    assert jeter_tour_bruit(texte, silence, mains_libres=True) is True


def test_phrase_nette_malgre_un_non_parole_eleve_n_est_pas_du_bruit():
    """Séance du 24 sept, 20 h : « Demande à Codex comment il va. » jeté comme
    bruit — no_speech_prob 0,95 mais décodage sûr (-0,34). La règle de Whisper
    exige les deux : non-parole probable ET décodage incertain."""
    segments = [{"no_speech_prob": 0.95, "avg_logprob": -0.34}]
    assert jeter_tour_bruit("Demande à Codex comment il va.", segments, mains_libres=True) is False


def test_realise_par_neo035_est_une_hallucination():
    assert est_hallucination_whisper("Réalisé par Neo035") is True
