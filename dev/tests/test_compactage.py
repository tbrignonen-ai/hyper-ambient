"""Contrat de la mémoire longue du host-agent."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.brain.contexte import estimer_jetons, fenetre_classifieur, projeter_messages, projeter_kw
from src.brain.compactage import BudgetModele, Compacteur, resume_message, est_nouvelle_conversation
from native.clibridge.conversation import message_pour_session


def _serve():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("serve_hostagent_compactage", root / "dev/scripts/serve_hostagent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_compactage_mlx_reutilise_modele_charge_et_fenetre_bornee(monkeypatch):
    import httpx
    from native.macos.profile import apply
    from src.brain.compactage import lire_fenetre_locale, resumer_local

    env = {"MOTHER_PROFILE": "mac-16g-voix-max"}
    apply(env)
    monkeypatch.setenv("COMPACTAGE_RESUMEUR_MODELE", env["COMPACTAGE_RESUMEUR_MODELE"])
    monkeypatch.setenv("LLAMA_SERVER_HOST", env["LLAMA_SERVER_HOST"])
    appels = []

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, json):
            appels.append((url, json))
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"choices": [{"message": {"content": "Mémoire stable"}}]})

        async def get(self, url):
            raise OSError("MLX n'expose pas /props ni /slots")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    assert await resumer_local("", [{"role": "user", "content": "Bonjour"}]) == "Mémoire stable"
    assert appels[0][0] == "http://127.0.0.1:8080/v1/chat/completions"
    assert appels[0][1]["model"] == "default_model"
    assert appels[0][1]["chat_template_kwargs"] == {"enable_thinking": False}
    modele = SimpleNamespace(api_endpoint=env["BRAIN_API_ENDPOINT"], n_ctx=2048)
    assert await lire_fenetre_locale(modele) == 2048


def test_resume_survit_projection_et_classifieur():
    summary = resume_message("Thomas a une soutenance à 14 h.")
    history = [summary] + [m for i in range(20) for m in (
        {"role": "user", "content": f"Question {i} " + "x" * 100},
        {"role": "assistant", "content": f"Réponse {i}"},
    )]
    for channel in ("reflex", "deep"):
        projected = projeter_messages(history, channel)
        assert projected[0] == summary
        assert estimer_jetons(projected) <= (512 if channel == "reflex" else 3000)
    assert "soutenance" not in fenetre_classifieur("oui", [summary])


def test_modele_large_utilise_son_budget_au_dela_de_quinze_tours():
    history = [m for i in range(20) for m in (
        {"role": "user", "content": f"Q{i}"},
        {"role": "assistant", "content": f"R{i}"},
    )]
    projection = projeter_messages(history, "deep", BudgetModele(32768, 3000))
    assert len(projection) == 40


def test_budget_reflexe_borne_historique_et_tour_courant():
    history = [resume_message("Thomas a une soutenance à 14 h. " + "a" * 350)]
    history += [m for i in range(6) for m in (
        {"role": "user", "content": "question " + "b" * 60},
        {"role": "assistant", "content": "réponse " + "c" * 60},
    )]
    messages = [{"role": "system", "content": "Instructions " + "z" * 250},
                *history, {"role": "user", "content": "Merci."}]
    projected = projeter_kw({"history": history, "messages": messages}, "reflex", BudgetModele(4096, 256))
    assert estimer_jetons(projected["messages"][1:]) <= 256
    assert estimer_jetons(projected["messages"]) <= 4096


@pytest.mark.asyncio
async def test_40_echanges_fait_du_second_restitue_aux_deux_canaux():
    async def summarizer(previous, evicted):
        facts = [m["content"] for m in evicted if "soutenance" in m["content"]]
        return " ".join([previous, *facts]).strip()

    compact = Compacteur(BudgetModele(4096, 512), summarizer=summarizer, garder_tours=3)
    for i in range(1, 41):
        question = "Je m'appelle Thomas, ma soutenance est à 14 h." if i == 2 else f"Échange {i} " + "bla " * 35
        compact.retenir(question, f"Réponse {i}.")
        compact.planifier()
        await compact.attendre()
    for channel in ("reflex", "deep"):
        projection = projeter_messages(compact.messages(), channel)
        assert "soutenance" in " ".join(m["content"] for m in projection)
    assert len(compact.resume) <= 700
    assert estimer_jetons(projeter_messages(compact.messages(), "reflex")) <= 512


@pytest.mark.asyncio
async def test_fait_utilisateur_survit_a_un_resume_qui_l_omet():
    async def summarizer(previous, evicted):
        return "Suivi du projet."
    compact = Compacteur(BudgetModele(4096, 256), summarizer=summarizer)
    compact.retenir("Bonjour", "Bonjour")
    compact.retenir("Je m'appelle Thomas et ma soutenance est à 14 h.", "Compris")
    for i in range(12):
        compact.retenir("Suivi " + "x" * 120, "D'accord")
        compact.planifier()
        await compact.attendre()
    assert "Thomas" in compact.resume and "14 h" in compact.resume


@pytest.mark.asyncio
async def test_echec_ne_perd_pas_les_tours_et_retente():
    calls = 0
    async def summarizer(previous, evicted):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("service indisponible")
        return "Thomas a une soutenance à 14 h."
    compact = Compacteur(BudgetModele(4096, 200), summarizer=summarizer, garder_tours=2)
    for i in range(8):
        compact.retenir("fait important " + "x" * 100, "réponse")
    before = len(compact.historique)
    compact.planifier()
    await compact.attendre()
    assert len(compact.historique) == before
    compact.planifier()
    await compact.attendre()
    assert calls == 2 and compact.resume


@pytest.mark.asyncio
async def test_resume_hors_chemin_critique_et_non_recompacte():
    signal = asyncio.Event()
    evicted_roles = []
    async def summarizer(previous, evicted):
        evicted_roles.extend(m["role"] for m in evicted)
        await signal.wait()
        return "Mémoire courte"
    compact = Compacteur(BudgetModele(4096, 256), summarizer=summarizer)
    for i in range(10):
        compact.retenir("Question " + "x" * 120, "Réponse")
    compact.planifier()
    assert not compact._tache.done()
    assert len(compact.historique) == 20
    signal.set()
    await compact.attendre()
    assert compact.resume and "system" not in evicted_roles


@pytest.mark.asyncio
async def test_reprise_bornee_apres_longue_panne():
    batches = []
    async def summarizer(previous, evicted):
        batches.append(sum(len(m["content"]) for m in evicted))
        return "Mémoire stable"
    compact = Compacteur(BudgetModele(4096, 256), summarizer=summarizer)
    for i in range(100):
        compact.retenir(f"Question {i} " + "x" * 150, "Réponse")
    for _ in range(10):
        compact.planifier()
        await compact.attendre()
    assert max(batches) <= 6000
    assert len(compact.historique) >= 6


@pytest.mark.asyncio
async def test_host_compacte_apres_purge_des_outils_ephemeres():
    pipeline = _serve().HostPipeline()
    pipeline.brain = SimpleNamespace(reflex=SimpleNamespace(model="local", n_ctx=4096))
    vus = []
    async def summarizer(previous, evicted):
        vus.extend(m["content"] for m in evicted)
        return "Thomas a une soutenance à 14 h."
    pipeline._compacteur.summarizer = summarizer
    pipeline._compacteur.budget = BudgetModele(4096, 200)
    for i in range(8):
        pipeline._historique.extend([{"role": "user", "content": "Question " + "x" * 300},
                                     {"role": "assistant", "content": "Réponse"}])
    ephemere = {"role": "assistant", "content": "résultat éphémère SECRET"}
    pipeline._historique.append(ephemere)
    pipeline._historique_outils_ephemeres.append(ephemere)
    pipeline._purger_historique_outils_ephemere()
    await pipeline._compacteur.attendre()
    assert "SECRET" not in " ".join(vus)
    assert pipeline._historique_pour_modele()[0]["compactage_resume"]


def test_pont_abonnement_ignore_resume_sur_session_existante():
    messages = [resume_message("Thomas a une soutenance à 14 h."),
                {"role": "assistant", "content": "Ancienne réponse"},
                {"role": "user", "content": "Et maintenant ?"}]
    texte, neuve = message_pour_session(messages, "Ancienne réponse")
    assert not neuve and "soutenance" not in texte
    texte_neuf, neuve = message_pour_session(messages, None)
    assert neuve and "soutenance" in texte_neuf


def test_host_injecte_resume_et_reinitialise():
    pipeline = _serve().HostPipeline()
    pipeline._compacteur.resume = "Thomas a une soutenance à 14 h."
    assert pipeline._historique_pour_modele()[0]["content"].endswith("14 h.")
    pipeline.nouvelle_conversation()
    assert pipeline._historique_pour_modele() == []


def test_host_borne_aussi_le_canal_direct():
    pipeline = _serve().HostPipeline()
    pipeline.brain = SimpleNamespace(model="MiniMaxAI/MiniMax-M3", name="openai-compat")
    pipeline._compacteur.resume = "Thomas a une soutenance à 14 h."
    pipeline._historique = [m for i in range(40) for m in (
        {"role": "user", "content": "Question " + "x" * 250},
        {"role": "assistant", "content": "Réponse " + "y" * 100},
    )]
    projection = pipeline._historique_pour_modele()
    assert projection[0]["compactage_resume"]
    assert estimer_jetons(projection) <= 3000


@pytest.mark.parametrize("commande", ["nouvelle conversation", "Ouvre une nouvelle conversation", "new conversation", "start a new conversation", "nueva conversación", "inicia una nueva conversación"])
def test_commande_vocale_trois_langues(commande):
    assert est_nouvelle_conversation(commande)
    assert not est_nouvelle_conversation("Demande à Claude une nouvelle session")


@pytest.mark.asyncio
async def test_une_purge_pendant_le_resume_ne_fait_pas_retirer_les_tours_recents():
    """Le résumé retire les messages résumés eux-mêmes, pas un nombre de positions."""
    feu = asyncio.Event()

    async def lent(ancien, echanges):
        await feu.wait()
        return "résumé"

    compacteur = Compacteur(BudgetModele(4096, 128), summarizer=lent, garder_tours=1)
    for i in range(4):
        compacteur.retenir(f"question {i} " + "x" * 400, f"réponse {i} " + "y" * 400)
    compacteur.planifier()
    await asyncio.sleep(0)
    # Une purge d'outils éphémères retire l'échange 0 pendant le résumé.
    del compacteur.historique[:2]
    feu.set()
    await compacteur.attendre()
    contenus = [m["content"][:10] for m in compacteur.historique]
    assert any(c.startswith("question 3") for c in contenus)
    assert any(c.startswith("réponse 3") for c in contenus)
    assert not any(c.startswith("question 1") for c in contenus)
