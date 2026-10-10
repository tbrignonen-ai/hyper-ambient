"""Accueil guidé par le modèle (V1) : logique pure, sondes injectées.

Règle d'or : jamais « connecté » sans preuve. Chaque test fournit un faux
requêteur ; aucun appel réseau, aucune dépendance Tk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
for chemin in (str(RACINE), str(RACINE / "native" / "presence")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from native.presence import onboarding as classique  # noqa: E402
from native.presence import onboarding_llm as llm  # noqa: E402


class FauxRequeteur:
    """Rend une réponse préparée par URL et garde trace des requêtes."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.requetes: list[llm.Requete] = []

    def __call__(self, requete: llm.Requete) -> llm.Reponse:
        self.requetes.append(requete)
        reponse = self.reponses.get(requete.url)
        if reponse is None:
            return llm.Reponse(statut=None, corps="", latence_ms=1.0, erreur="connexion refusée")
        return reponse


def ok(corps="", statut=200, latence=42.0):
    return llm.Reponse(statut=statut, corps=corps, latence_ms=latence, erreur=None)


URL_CODEX = "http://127.0.0.1:8765/ask"
URL_CLAUDE = "http://127.0.0.1:8766/ask"
JETONS = {"CODEX_BRIDGE_TOKEN": "jeton-codex", "CLI_BRIDGE_TOKEN": "jeton-cli"}


# --- Étapes et libellés ------------------------------------------------------

def test_quatre_etapes_dans_l_ordre():
    assert llm.ETAPES_LLM == ("declarer", "guider", "armer", "essayer")


def test_le_wizard_classique_reste_inchange():
    assert classique.ETAPES_WIZARD == ("bienvenue", "mains_libres", "ptt", "masquage")


@pytest.mark.parametrize(
    ("pont", "jeton", "pong", "couleur", "libelle"),
    [
        (True, True, True, llm.VERT, "Connecté — PONG reçu"),
        (False, None, None, llm.ROUGE, "Pont fermé"),
        (True, False, None, llm.ROUGE, "Token refusé"),
        (True, True, False, llm.ROUGE, "Pas de PONG"),
        (None, None, None, llm.GRIS, "Non vérifié"),
    ],
)
def test_etat_harnais_et_libelle_francais(pont, jeton, pong, couleur, libelle):
    etat = llm.etat_depuis_indicateurs(pont=pont, jeton=jeton, pong=pong)
    assert etat.couleur == couleur
    assert llm.libelle_etat(etat) == libelle


def test_vert_exige_les_trois_preuves():
    for pont, jeton, pong in [
        (True, True, None), (True, None, True), (None, True, True), (True, True, False),
    ]:
        assert llm.etat_depuis_indicateurs(pont=pont, jeton=jeton, pong=pong).couleur != llm.VERT


def test_un_etat_vert_ne_peut_pas_etre_construit_sans_preuve():
    with pytest.raises(ValueError):
        llm.EtatHarnais(couleur=llm.VERT, cause="", pont=True, jeton=True, pong=False)


# --- Déclarer ------------------------------------------------------------------

def test_url_sante_depuis_l_adresse_chat_completions():
    assert llm.url_sante("https://api.exemple/v1/chat/completions") == "https://api.exemple/v1/models"
    assert llm.url_sante("https://api.exemple/v1/") == "https://api.exemple/v1/models"


def test_declarer_sante_200_verifie_avec_statut_et_latence():
    decl = llm.DeclarationDistant(nom="MiniMax-M3", url="https://api.exemple/v1", cle="sk-secret")
    requeteur = FauxRequeteur({"https://api.exemple/v1/models": ok(statut=200, latence=123.4)})
    resultat = llm.verifier_distant(decl, requeteur)
    assert resultat.verifie is True
    assert resultat.statut == 200
    assert resultat.latence_ms == pytest.approx(123.4)
    assert "HTTP 200" in resultat.message and "123 ms" in resultat.message
    requete = requeteur.requetes[0]
    assert requete.methode == "GET"
    assert requete.entetes.get("Authorization") == "Bearer sk-secret"


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [
        (ok(statut=401), "HTTP 401"),
        (ok(statut=503), "HTTP 503"),
        (None, "Injoignable"),
    ],
)
def test_declarer_echec_reste_non_verifie(reponse, attendu):
    decl = llm.DeclarationDistant(nom="MiniMax-M3", url="https://api.exemple/v1", cle="sk")
    reponses = {} if reponse is None else {"https://api.exemple/v1/models": reponse}
    resultat = llm.verifier_distant(decl, FauxRequeteur(reponses))
    assert resultat.verifie is False
    assert attendu in resultat.message
    assert "non vérifié" in resultat.message


def test_declarer_sans_url_ne_sonde_rien():
    requeteur = FauxRequeteur({})
    resultat = llm.verifier_distant(llm.DeclarationDistant(nom="", url="", cle=""), requeteur)
    assert resultat.verifie is False
    assert requeteur.requetes == []


def test_les_secrets_vont_dans_env_local_seulement(tmp_path):
    env_local = tmp_path / ".env.local"
    presence = tmp_path / "presence.json"
    decl = llm.DeclarationDistant(nom="MiniMax-M3", url="https://api.exemple/v1", cle="sk-secret")
    llm.enregistrer_declaration(decl, env_local)
    etat = llm.EtatOnboardingLLM(etape="guider", distant_verifie=True)
    llm.enregistrer_onboarding_llm(etat, presence)
    texte_env = env_local.read_text(encoding="utf-8")
    assert "BRAIN_API_KEY=sk-secret" in texte_env
    assert "BRAIN_API_ENDPOINT=https://api.exemple/v1" in texte_env
    assert "BRAIN_MODEL=MiniMax-M3" in texte_env
    texte_presence = presence.read_text(encoding="utf-8")
    assert "sk-secret" not in texte_presence
    assert "api.exemple" not in texte_presence


def test_declarer_est_passable():
    etat = llm.passer_etape(llm.EtatOnboardingLLM(), "declarer")
    assert etat.etape == "guider"
    assert etat.distant_verifie is False


# --- Guider --------------------------------------------------------------------

def test_guider_propose_une_liste_non_cochee():
    items = llm.proposer_checklist(proposer=None)
    assert [i.cle for i in items] == ["codex", "claude", "distant"]
    assert all(i.coche is False for i in items)
    textes = " ".join(i.texte for i in items).lower()
    assert "fichiers" in textes and "relecture" in textes and "raisonnement" in textes


def test_guider_utilise_le_cerveau_local_quand_il_repond():
    items = llm.proposer_checklist(proposer=lambda: {"codex": "Codex lit et modifie les fichiers."})
    assert items[0].texte == "Codex lit et modifie les fichiers."
    assert items[0].coche is False


def test_guider_cerveau_local_en_panne_rend_la_liste_par_defaut():
    def panne():
        raise OSError("cerveau local absent")

    items = llm.proposer_checklist(proposer=panne)
    assert [i.cle for i in items] == ["codex", "claude", "distant"]


def test_cocher_n_arme_rien():
    etat = llm.EtatOnboardingLLM()
    etat = llm.cocher(etat, "codex", True)
    assert etat.guide_coche == ("codex",)
    assert etat.armes == {}
    assert all(e.couleur == llm.GRIS for e in llm.etats_initiaux(etat).values())


# --- Armer ---------------------------------------------------------------------

def test_armer_codex_pong_recu_passe_au_vert():
    requeteur = FauxRequeteur({URL_CODEX: ok(json.dumps({"answer": "PONG"}))})
    etat = llm.sonder_harnais("codex", JETONS, requeteur)
    assert etat.couleur == llm.VERT
    requete = requeteur.requetes[0]
    assert requete.methode == "POST"
    assert requete.entetes["Authorization"] == "Bearer jeton-codex"
    assert requete.corps == {"question": "PONG"}


def test_armer_claude_envoie_agent_claude():
    requeteur = FauxRequeteur({URL_CLAUDE: ok("PONG")})
    etat = llm.sonder_harnais("claude", JETONS, requeteur)
    assert etat.couleur == llm.VERT
    requete = requeteur.requetes[0]
    assert requete.corps == {"question": "PONG", "agent": "claude"}
    assert requete.entetes["Authorization"] == "Bearer jeton-cli"


def test_armer_refuse_le_vert_sans_pong():
    requeteur = FauxRequeteur({URL_CODEX: ok(json.dumps({"answer": "Bonjour !"}))})
    etat = llm.sonder_harnais("codex", JETONS, requeteur)
    assert etat.couleur == llm.ROUGE
    assert llm.libelle_etat(etat) == "Pas de PONG"


def test_armer_pont_ferme():
    etat = llm.sonder_harnais("codex", JETONS, FauxRequeteur({}))
    assert etat.couleur == llm.ROUGE
    assert llm.libelle_etat(etat) == "Pont fermé"


@pytest.mark.parametrize("statut", [401, 403])
def test_armer_token_refuse(statut):
    etat = llm.sonder_harnais("claude", JETONS, FauxRequeteur({URL_CLAUDE: ok("PONG", statut=statut)}))
    assert etat.couleur == llm.ROUGE
    assert llm.libelle_etat(etat) == "Token refusé"


def test_armer_sans_jeton_ne_sonde_pas_et_reste_rouge():
    requeteur = FauxRequeteur({URL_CODEX: ok("PONG")})
    etat = llm.sonder_harnais("codex", {}, requeteur)
    assert etat.couleur == llm.ROUGE
    assert requeteur.requetes == []
    assert "token" in llm.libelle_etat(etat).lower()


def test_armer_distant_par_la_sante():
    requeteur = FauxRequeteur({"https://api.exemple/v1/models": ok(statut=200)})
    etat = llm.sonder_harnais(
        "distant", {"BRAIN_API_ENDPOINT": "https://api.exemple/v1", "BRAIN_API_KEY": "sk"}, requeteur
    )
    assert etat.couleur == llm.VERT
    assert requeteur.requetes[0].methode == "GET"


def test_armer_un_par_un():
    requeteur = FauxRequeteur({URL_CODEX: ok("PONG"), URL_CLAUDE: ok("PONG")})
    etat = llm.armer(llm.EtatOnboardingLLM(), "codex", JETONS, requeteur)
    assert etat.armes == {"codex": True}
    assert [r.url for r in requeteur.requetes] == [URL_CODEX]


def test_armer_echec_ne_marque_pas_arme():
    etat = llm.armer(llm.EtatOnboardingLLM(), "codex", JETONS, FauxRequeteur({}))
    assert etat.armes == {"codex": False}


# --- Essayer -------------------------------------------------------------------

def test_essayer_reponse_reelle_du_harnais():
    evenements = [
        {"type": "etat", "etat": "harnais"},
        {"type": "rapport", "transcript": "Codex, réponds PONG", "reply": "PONG, je suis là."},
        {"type": "premier_son", "ms": 640.0},
    ]
    resultat = llm.evaluer_tour("codex", evenements)
    assert resultat.reussi is True
    assert resultat.texte_affiche == "PONG, je suis là."
    assert resultat.a_dire is None  # le pipeline l'a déjà dit
    assert resultat.eclair == "harnais"


def test_essayer_distant_allume_l_eclair():
    evenements = [
        {"type": "etat", "etat": "escalade"},
        {"type": "rapport", "transcript": "question", "reply": "Réponse longue."},
        {"type": "premier_son", "ms": 900.0},
    ]
    resultat = llm.evaluer_tour("distant", evenements)
    assert resultat.reussi is True
    assert resultat.eclair == "escalade"
    assert classique.eclair_allume(resultat.eclair)


def test_essayer_repli_visible_et_parle_quand_rien_ne_revient():
    resultat = llm.evaluer_tour("codex", [{"type": "statut", "texte": "Aucune trame de réponse — rien à restituer."}])
    assert resultat.reussi is False
    assert resultat.repli is True
    assert resultat.texte_affiche
    assert resultat.a_dire == resultat.texte_affiche
    assert "je reste en local" in resultat.a_dire


def test_essayer_reponse_locale_n_est_pas_un_succes_du_harnais():
    evenements = [
        {"type": "etat", "etat": "reflexion"},
        {"type": "rapport", "transcript": "Codex, réponds PONG", "reply": "Je ne peux pas joindre Codex."},
        {"type": "premier_son", "ms": 500.0},
    ]
    resultat = llm.evaluer_tour("codex", evenements)
    assert resultat.reussi is False
    assert resultat.repli is True
    assert "Je ne peux pas joindre Codex." in resultat.texte_affiche
    assert resultat.a_dire is None  # la voix a déjà parlé : pas de doublon
    assert resultat.eclair is None


def test_essayer_reponse_sans_voix_est_dite_par_presence():
    evenements = [
        {"type": "etat", "etat": "harnais"},
        {"type": "rapport", "transcript": "x", "reply": "PONG"},
    ]
    resultat = llm.evaluer_tour("codex", evenements)
    assert resultat.texte_affiche == "PONG"
    assert resultat.a_dire == "PONG"


def test_essayer_un_harnais_non_arme_rend_le_repli_sans_tour():
    resultat = llm.repli_non_arme("claude", llm.etat_depuis_indicateurs(pont=False, jeton=None, pong=None))
    assert resultat.reussi is False
    assert resultat.a_dire == resultat.texte_affiche
    assert "pont fermé" in resultat.a_dire.lower()
    assert "je reste en local" in resultat.a_dire


# --- Persistance ---------------------------------------------------------------

def test_persistance_sous_une_cle_separee(tmp_path):
    chemin = tmp_path / "presence.json"
    classique.enregistrer_configuration(
        classique.ConfigurationPresence(onboarding_termine=True, raccourci_ptt="ctrl-space"), chemin
    )
    llm.enregistrer_onboarding_llm(
        llm.EtatOnboardingLLM(etape="armer", distant_verifie=True, guide_coche=("codex",), armes={"codex": True}),
        chemin,
    )
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    assert brut["onboarding_termine"] is True
    assert brut["raccourci_ptt"] == "ctrl-space"
    assert brut["onboarding_llm"]["etape"] == "armer"
    assert "onboarding_termine" not in brut["onboarding_llm"]

    # Le wizard classique réécrit sa configuration sans effacer la clé LLM.
    classique.enregistrer_configuration(
        classique.ConfigurationPresence(onboarding_termine=True, raccourci_ptt="space"), chemin
    )
    relu = llm.charger_onboarding_llm(chemin)
    assert relu.etape == "armer"
    assert relu.armes == {"codex": True}
    assert classique.charger_configuration(chemin).raccourci_ptt == "space"


def test_l_onboarding_llm_ne_termine_pas_le_classique(tmp_path):
    chemin = tmp_path / "presence.json"
    llm.enregistrer_onboarding_llm(llm.EtatOnboardingLLM(etape="essayer", termine=True), chemin)
    assert classique.charger_configuration(chemin).onboarding_termine is False


def test_charger_sans_fichier_ou_corrompu(tmp_path):
    assert llm.charger_onboarding_llm(tmp_path / "absent.json") == llm.EtatOnboardingLLM()
    corrompu = tmp_path / "presence.json"
    corrompu.write_text("{pas du json", encoding="utf-8")
    assert llm.charger_onboarding_llm(corrompu) == llm.EtatOnboardingLLM()
    corrompu.write_text(json.dumps({"onboarding_llm": {"etape": "inconnue", "armes": "x"}}), encoding="utf-8")
    assert llm.charger_onboarding_llm(corrompu).etape == "declarer"


def test_un_harnais_arme_hier_redevient_gris_au_relancement(tmp_path):
    """Jamais vert sans preuve : la persistance ne remplace pas une sonde."""
    chemin = tmp_path / "presence.json"
    llm.enregistrer_onboarding_llm(llm.EtatOnboardingLLM(armes={"codex": True}), chemin)
    etats = llm.etats_initiaux(llm.charger_onboarding_llm(chemin))
    assert etats["codex"].couleur == llm.GRIS
    assert llm.libelle_etat(etats["codex"]) == "Non vérifié"
