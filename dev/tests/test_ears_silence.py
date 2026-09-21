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
