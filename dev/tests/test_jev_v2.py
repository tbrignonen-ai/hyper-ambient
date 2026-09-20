"""Regle addressed_v2 : aucun reseau, dictionnaires de reponses seulement."""
from __future__ import annotations

import asyncio

from src.ears.jev_reflexe import (
    QUESTIONS,
    SEUIL_DEMANDE,
    SEUIL_INTERPELLATION,
    SEUIL_LU_DIFFUSE,
    SEUIL_MONOLOGUE,
    SEUIL_NOM_PRONONCE,
    SEUIL_PAROLE_RAPPORTEE,
    SEUIL_TIERS,
    JevReflexe,
    addressed_v2,
)
from test_jev_reflexe import FakeResponse, FakeTransport, _answers


def _a(
    *,
    nom: float = 0.0,
    interp: float = 0.0,
    demande: float = 0.0,
    tiers: float = 0.0,
    lu: float = 0.0,
    rapporte: float = 0.0,
    mono: float = 0.0,
) -> dict[str, dict[str, float]]:
    return {
        "assistant_name_spoken": {"noul": nom},
        "direct_interpellation": {"noul": interp},
        "request_or_command": {"noul": demande},
        "third_party_conversation": {"noul": tiers},
        "read_broadcast_recited": {"noul": lu},
        "reported_or_quoted_speech": {"noul": rapporte},
        "unaddressed_self_talk": {"noul": mono},
    }


# Mesure 2026-09-20, scores N/I/D/T/L/R/S. Voir OUT-JEV-QUESTIONS-V2.
_MESURE_ADRESSEES = (
    (0.02, 0.95, 0.99, 0.35, 0.10, 0.11, 0.02),  # est-ce que tu m'entends ?
    (0.95, 0.03, 0.03, 0.09, 0.52, 0.21, 0.77),  # hyper ambiant
    (0.02, 0.95, 0.02, 0.17, 0.15, 0.12, 0.12),  # bonjour
    (0.03, 0.96, 0.02, 0.24, 0.14, 0.09, 0.11),  # salut
    (0.02, 0.96, 0.03, 0.20, 0.09, 0.08, 0.13),  # hey
    (0.03, 0.88, 0.06, 0.15, 0.11, 0.12, 0.42),  # bon je teste… bonjour
    (0.02, 0.96, 0.96, 0.44, 0.12, 0.14, 0.02),  # tu m'entends ?
    (0.93, 0.89, 0.96, 0.09, 0.21, 0.14, 0.12),  # Hyper Ambient, quelle heure
    (0.80, 0.98, 0.98, 0.55, 0.14, 0.34, 0.02),  # MOTHER, allume la lumiere
    (0.86, 0.85, 0.95, 0.27, 0.11, 0.14, 0.21),  # HA, cherche la meteo
    (0.95, 0.96, 0.05, 0.17, 0.30, 0.13, 0.14),  # coucou Hyper Ambient
    (0.03, 0.98, 0.97, 0.18, 0.08, 0.08, 0.03),  # dis-moi la temperature
    (0.03, 0.59, 0.97, 0.30, 0.28, 0.18, 0.17),  # arrete
    (0.03, 0.07, 0.53, 0.25, 0.51, 0.40, 0.65),  # attends
    (0.03, 0.95, 0.98, 0.11, 0.06, 0.07, 0.02),  # peux-tu noter…
    (0.02, 0.20, 0.98, 0.08, 0.10, 0.07, 0.11),  # quel temps fera-t-il demain ?
    (0.03, 0.49, 0.96, 0.11, 0.09, 0.07, 0.13),  # ouvre le calendrier
    (0.03, 0.87, 0.97, 0.11, 0.08, 0.06, 0.04),  # aide-moi avec ce document
    (0.02, 0.21, 0.89, 0.05, 0.06, 0.05, 0.08),  # je voudrais une recette
    (0.03, 0.97, 0.70, 0.30, 0.06, 0.09, 0.03),  # ecoute, j'ai une question
    (0.02, 0.94, 0.02, 0.20, 0.14, 0.09, 0.13),  # bonsoir
    (0.02, 0.96, 0.71, 0.30, 0.11, 0.13, 0.10),  # allo ?
    (0.03, 0.95, 0.97, 0.22, 0.10, 0.10, 0.03),  # reponds-moi
    (0.03, 0.94, 0.98, 0.28, 0.06, 0.08, 0.02),  # tu peux repeter ?
)

_MESURE_NON_ADRESSEES = (
    (0.03, 0.11, 0.28, 0.45, 0.83, 0.16, 0.30),  # place au film
    (0.03, 0.03, 0.02, 0.18, 0.97, 0.35, 0.56),  # Realise par…
    (0.02, 0.34, 0.06, 0.70, 0.19, 0.55, 0.42),  # module deux
    (0.02, 0.82, 0.04, 0.77, 0.07, 0.14, 0.04),  # je t'envoie le document
    (0.02, 0.03, 0.02, 0.39, 0.35, 0.19, 0.73),  # le train part
    (0.02, 0.03, 0.02, 0.19, 0.22, 0.13, 0.81),  # il fait beau
    (0.02, 0.03, 0.03, 0.21, 0.14, 0.14, 0.84),  # je vais prendre du pain
    (0.08, 0.05, 0.02, 0.88, 0.56, 0.19, 0.45),  # chanson dediee a Marie
    (0.02, 0.02, 0.02, 0.23, 0.68, 0.27, 0.71),  # chapitre trois
    (0.03, 0.87, 0.96, 0.33, 0.69, 0.68, 0.03),  # repetez apres moi
    (0.05, 0.99, 0.98, 0.78, 0.07, 0.19, 0.01),  # Julie, tu peux fermer
    (0.03, 0.99, 0.95, 0.84, 0.09, 0.31, 0.01),  # salut Marc
    (0.03, 0.04, 0.03, 0.43, 0.15, 0.18, 0.78),  # appeler maman
    (0.02, 0.42, 0.04, 0.42, 0.91, 0.39, 0.20),  # ce soir dans votre journal
    (0.02, 0.64, 0.97, 0.43, 0.79, 0.22, 0.05),  # abonnez-vous
    (0.02, 0.87, 0.60, 0.50, 0.28, 0.98, 0.02),  # il a demande : tu m'entends ?
    (0.02, 0.03, 0.02, 0.25, 0.35, 0.54, 0.78),  # la meteo annonce
    (0.03, 0.03, 0.04, 0.18, 0.14, 0.12, 0.82),  # je dois repondre a ce mail
    (0.02, 0.27, 0.14, 0.67, 0.17, 0.18, 0.14),  # on se retrouve a dix heures
    (0.03, 0.56, 0.03, 0.58, 0.35, 0.21, 0.04),  # merci a tous
    (0.03, 0.92, 0.03, 0.49, 0.92, 0.19, 0.11),  # bonjour et bienvenue
    (0.02, 0.04, 0.09, 0.45, 0.39, 0.96, 0.73),  # le professeur a dit
)


def test_nom_prononce_seul_adresse_meme_si_tout_le_reste_est_bas():
    assert addressed_v2(_a(nom=SEUIL_NOM_PRONONCE, mono=0.99, lu=0.99, rapporte=0.99, tiers=0.99))
    assert addressed_v2(_a(nom=0.95))


def test_interpellation_forte_sans_nom_adresse():
    assert addressed_v2(_a(interp=0.95))


def test_demande_forte_sans_nom_adresse():
    assert addressed_v2(_a(demande=0.89))


def test_interpellation_forte_mais_tiers_eleve_non_adresse():
    assert not addressed_v2(_a(interp=0.82, tiers=0.77))


def test_parole_rapportee_elevee_non_adresse():
    assert not addressed_v2(_a(interp=0.87, demande=0.60, rapporte=0.98))


def test_contenu_diffuse_lu_eleve_non_adresse():
    assert not addressed_v2(_a(interp=0.92, lu=0.92))


def test_tout_bas_non_adresse():
    assert not addressed_v2(_a())


def test_seuil_nom_juste_dessous_et_dessus():
    assert not addressed_v2(_a(nom=SEUIL_NOM_PRONONCE - 0.01))
    assert addressed_v2(_a(nom=SEUIL_NOM_PRONONCE))


def test_seuil_interpellation_juste_dessous_et_dessus():
    assert not addressed_v2(_a(interp=SEUIL_INTERPELLATION - 0.01))
    assert addressed_v2(_a(interp=SEUIL_INTERPELLATION))


def test_seuil_demande_juste_dessous_et_dessus():
    assert not addressed_v2(_a(demande=SEUIL_DEMANDE - 0.01))
    assert addressed_v2(_a(demande=SEUIL_DEMANDE))


def test_seuil_tiers_juste_dessous_et_dessus():
    assert addressed_v2(_a(interp=SEUIL_INTERPELLATION, tiers=SEUIL_TIERS - 0.01))
    assert not addressed_v2(_a(interp=SEUIL_INTERPELLATION, tiers=SEUIL_TIERS))


def test_seuil_lu_diffuse_juste_dessous_et_dessus():
    assert addressed_v2(_a(interp=SEUIL_INTERPELLATION, lu=SEUIL_LU_DIFFUSE - 0.01))
    assert not addressed_v2(_a(interp=SEUIL_INTERPELLATION, lu=SEUIL_LU_DIFFUSE))


def test_seuil_parole_rapportee_juste_dessous_et_dessus():
    assert addressed_v2(_a(interp=SEUIL_INTERPELLATION, rapporte=SEUIL_PAROLE_RAPPORTEE - 0.01))
    assert not addressed_v2(_a(interp=SEUIL_INTERPELLATION, rapporte=SEUIL_PAROLE_RAPPORTEE))


def test_seuil_monologue_juste_dessous_et_dessus():
    assert addressed_v2(_a(interp=SEUIL_INTERPELLATION, mono=SEUIL_MONOLOGUE - 0.01))
    assert not addressed_v2(_a(interp=SEUIL_INTERPELLATION, mono=SEUIL_MONOLOGUE))


def test_mesure_zero_faux_negatif_sur_vingt_quatre_adressees():
    assert len(_MESURE_ADRESSEES) == 24
    faux_negatifs = [
        scores
        for scores in _MESURE_ADRESSEES
        if not addressed_v2(
            _a(
                nom=scores[0],
                interp=scores[1],
                demande=scores[2],
                tiers=scores[3],
                lu=scores[4],
                rapporte=scores[5],
                mono=scores[6],
            )
        )
    ]
    assert faux_negatifs == []


def test_mesure_zero_faux_positif_sur_vingt_deux_non_adressees():
    assert len(_MESURE_NON_ADRESSEES) == 22
    faux_positifs = [
        scores
        for scores in _MESURE_NON_ADRESSEES
        if addressed_v2(
            _a(
                nom=scores[0],
                interp=scores[1],
                demande=scores[2],
                tiers=scores[3],
                lu=scores[4],
                rapporte=scores[5],
                mono=scores[6],
            )
        )
    ]
    assert faux_positifs == []


def test_questions_v2_remplacent_addressed_to_mother_et_gardent_le_reste():
    attendus = (
        "assistant_name_spoken",
        "direct_interpellation",
        "request_or_command",
        "third_party_conversation",
        "read_broadcast_recited",
        "reported_or_quoted_speech",
        "unaddressed_self_talk",
    )
    assert "addressed_to_mother" not in QUESTIONS
    for identifiant in attendus:
        assert QUESTIONS[identifiant]["type"] == "noul"
    for conservee in (
        "real_interruption",
        "phrase_finished",
        "transcription_uncertain",
        "expected_response_length",
        "tone",
        "frustration",
        "needs_current_information",
        "refers_to_context",
        "requests_memory",
        "sensitive_local_action",
        "contains_personal_data",
        "named_harness",
    ):
        assert conservee in QUESTIONS
    assert len(QUESTIONS) == 19


def test_jev_signals_addressed_to_mother_suit_addressed_v2():
    """Le champ produit reste le meme ; seule la regle de calcul change."""
    nom_seul = _answers(assistant_name_spoken={"type": "noul", "noul": 0.50})
    transport = FakeTransport(FakeResponse(payload={"answers": nom_seul}))
    result = asyncio.run(JevReflexe(api_key="cle-de-test", transport=transport).evaluate("hyper ambiant"))
    assert result is not None
    assert result.signals.addressed_to_mother is True

    tout_bas = _answers()
    transport = FakeTransport(FakeResponse(payload={"answers": tout_bas}))
    result = asyncio.run(JevReflexe(api_key="cle-de-test", transport=transport).evaluate("il fait beau"))
    assert result is not None
    assert result.signals.addressed_to_mother is False
