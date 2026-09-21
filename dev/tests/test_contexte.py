"""Politique de contexte : spine, projections, classifieur, tampon, purge."""
from __future__ import annotations

from src.brain.contexte import (
    DUREE_SILENCE_BOUTON_S,
    DUREE_SILENCE_MAINS_LIBRES_S,
    JETONS_PROFOND,
    JETONS_REFLEXE,
    LONGUEUR_ANAPHORIQUE,
    LONGUEUR_ANAPHORE_AMBIANT,
    MEMOIRE_TOURS_PROFOND,
    SPINE_TOURS,
    TAMPON_AMBIANT_S,
    TRONCATURE_CLASSIFIEUR,
    MemoireConversation,
    TamponAmbiant,
    fenetre_classifieur,
    phrase_garde,
    projeter,
)


def _tour(i: int, origine="profond"):
    return {
        "user_norm": f"question numéro {i} sur le sujet",
        "assistant_spoken": f"réponse parlée numéro {i}",
        "origine": origine,
        "mandate_ref": None,
    }


def test_spine_garde_trois_tours_parles():
    memoire = MemoireConversation()
    for i in range(8):
        memoire.retenir(**_tour(i, origine="reflexe" if i < 3 else "profond"))
    spine = memoire.spine()
    assert len(spine) == SPINE_TOURS == 3
    assert "numéro 5" in spine[0]["user_norm"]
    assert "numéro 7" in spine[-1]["assistant_spoken"]
    for tour in spine:
        assert "résultat outil" not in tour["user_norm"]
        assert "{" not in tour["assistant_spoken"]


def test_projection_reflexe_borne_a_trois_tours():
    memoire = MemoireConversation()
    for i in range(10):
        memoire.retenir(**_tour(i))
    messages = projeter(memoire, canal="reflex")
    paires = [m for m in messages if m["role"] in {"user", "assistant"}]
    assert len(paires) == 6
    assert all("[résultat outil" not in m["content"] for m in messages)
    assert estimer_jetons(messages) <= JETONS_REFLEXE


def test_projection_profonde_garde_le_tour_ancien():
    memoire = MemoireConversation()
    memoire.retenir(
        user_norm="liste les fichiers de src/brain",
        assistant_spoken="quinze fichiers python",
        origine="profond",
    )
    for i in range(1, 12):
        memoire.retenir(**_tour(i))
    messages = projeter(memoire, canal="deep")
    textes = " ".join(m["content"] for m in messages)
    assert "quinze fichiers python" in textes
    assert "liste les fichiers de src/brain" in textes
    paires = [m for m in messages if m["role"] in {"user", "assistant"}]
    assert len(paires) <= MEMOIRE_TOURS_PROFOND * 2
    assert estimer_jetons(messages) <= JETONS_PROFOND


def estimer_jetons(messages):
    from src.brain.contexte import estimer_jetons as _est

    return _est(messages)


def test_classifieur_enonce_long_seul():
    memoire = MemoireConversation()
    memoire.retenir(user_norm="merci", assistant_spoken="je t'en prie", origine="reflexe")
    long = "Il est 14 heures 40, ma reunion commence dans 20 minutes ?"
    assert len(long) > LONGUEUR_ANAPHORIQUE
    fenetre = fenetre_classifieur(long, memoire)
    assert fenetre == long
    assert "merci" not in fenetre


def test_classifieur_anaphore_joint_le_tour_precedent():
    memoire = MemoireConversation()
    memoire.retenir(
        user_norm="x" * 200,
        assistant_spoken="y" * 200,
        origine="profond",
    )
    fenetre = fenetre_classifieur("vas-y", memoire)
    assert "vas-y" in fenetre
    assert "x" * 10 in fenetre
    assert "y" * 10 in fenetre
    assert len(fenetre) < 200 + 200 + 20


def test_tampon_ambiant_sert_une_anaphore_courte():
    tampon = TamponAmbiant()
    tampon.deposer("ferme la porte du bureau", maintenant=10.0)
    assert tampon.fournir("fais-le", maintenant=12.0) == "[ambiant] ferme la porte du bureau"
    assert tampon.fournir("fais-le", maintenant=12.0) is None


def test_tampon_ambiant_ignore_si_trop_vieux_ou_trop_long():
    tampon = TamponAmbiant()
    tampon.deposer("ferme la porte", maintenant=10.0)
    assert tampon.fournir("fais-le", maintenant=16.0) is None
    tampon.deposer("ferme la porte", maintenant=20.0)
    long = "peux-tu le faire maintenant s'il te plait"
    assert len(long) > LONGUEUR_ANAPHORE_AMBIANT
    assert tampon.fournir(long, maintenant=21.0) is None


def test_purge_vide_la_memoire_vive():
    memoire = MemoireConversation()
    tampon = TamponAmbiant()
    memoire.retenir(**_tour(1))
    tampon.deposer("bruit", maintenant=1.0)
    memoire.purger()
    tampon.oublier()
    assert memoire.spine() == []
    assert projeter(memoire, canal="deep") == []
    assert tampon.fournir("vas-y", maintenant=2.0) is None


def test_silence_mains_libres_reste_la_mesure_jev():
    assert DUREE_SILENCE_MAINS_LIBRES_S == 30.0
    assert DUREE_SILENCE_BOUTON_S == 60.0
    assert TAMPON_AMBIANT_S == 5.0


def test_phrase_garde_si_mandat_en_cours():
    assert "Codex" in phrase_garde(["Codex"])
    assert phrase_garde([]) == ""
