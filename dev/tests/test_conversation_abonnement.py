"""Mode abonnement : la conversation passe par le Claude Code de l'utilisateur.

Mesure du 24/09 : `claude -p` relancé à chaque tour coûte ~4,7 s, quel que
soit le modèle — c'est le démarrage. Une session gardée ouverte répond en
0,7 à 1 s. Le pont garde donc une session vivante et ne lui envoie que le
neuf ; le cerveau `abonnement` la consulte comme n'importe quel distant.
"""
import json

from native.clibridge.conversation import (
    MODELES_CLAUDE,
    SessionClaude,
    commande_session,
    message_pour_session,
)


def test_premier_tour_envoie_le_contexte_et_la_question():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "(Tâche confiée à Codex) 3 x 8"},
        {"role": "assistant", "content": "Codex a fini. 24"},
        {"role": "user", "content": "Il a dit quoi ?"},
    ]
    texte, neuve = message_pour_session(messages, derniere_reponse=None)
    assert neuve is True
    assert "Codex a fini. 24" in texte
    assert texte.rstrip().endswith("Il a dit quoi ?")


def test_tour_suivant_n_envoie_que_le_neuf():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour, je t'écoute."},
        {"role": "user", "content": "Quelle heure est-il ?"},
    ]
    texte, neuve = message_pour_session(messages, derniere_reponse="Bonjour, je t'écoute.")
    assert neuve is False
    assert texte == "Quelle heure est-il ?"


def test_ce_que_la_session_n_a_pas_vu_est_rappele():
    messages = [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour, je t'écoute."},
        {"role": "user", "content": "(Tâche confiée à Codex) 3 x 8"},
        {"role": "assistant", "content": "Codex a fini. 24"},
        {"role": "user", "content": "C'est juste ?"},
    ]
    texte, neuve = message_pour_session(messages, derniere_reponse="Bonjour, je t'écoute.")
    assert neuve is False
    assert "Codex a fini. 24" in texte
    assert texte.rstrip().endswith("C'est juste ?")


def test_historique_etranger_repart_d_une_session_neuve():
    messages = [{"role": "user", "content": "Nouvelle conversation"}]
    _, neuve = message_pour_session(messages, derniere_reponse="Ancienne réponse.")
    assert neuve is True


def test_commande_sans_reflexion_sans_contexte_du_depot():
    cmd = commande_session("claude", modele="haiku", systeme="SYS")
    assert cmd[0] == "claude"
    assert ["--model", "haiku"] == cmd[cmd.index("--model"):cmd.index("--model") + 2]
    assert "--input-format" in cmd and "stream-json" in cmd
    assert ["--effort", "low"] == cmd[cmd.index("--effort"):cmd.index("--effort") + 2]
    assert "--setting-sources" in cmd and "--strict-mcp-config" in cmd
    assert "--no-session-persistence" in cmd
    assert "SYS" in cmd
    assert "--permission-mode" not in cmd or "bypassPermissions" not in cmd


def test_session_rend_les_deltas_et_retient_sa_reponse():
    evenements = [
        {"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": "Oui, "}}},
        {"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": "je t'entends."}}},
        {"type": "result"},
    ]

    class _Proc:
        def __init__(self):
            self.ecrit = []
            self.stdout = iter(json.dumps(e) + "\n" for e in evenements)

            class _In:
                def write(inner, s):
                    self.ecrit.append(s)

                def flush(inner):
                    pass

            self.stdin = _In()

        def poll(self):
            return None

    procs = []

    def lancer(cmd, **kw):
        procs.append(_Proc())
        return procs[-1]

    session = SessionClaude(modele="haiku", lancer=lancer, reserve=False)
    morceaux = list(session.repondre([{"role": "user", "content": "Tu m'entends ?"}]))
    assert morceaux == ["Oui, ", "je t'entends."]
    assert session.derniere_reponse == "Oui, je t'entends."
    envoye = json.loads(procs[0].ecrit[0])
    assert envoye["message"]["content"].endswith("Tu m'entends ?")


def test_modeles_claude_proposes():
    ids = [m["id"] for m in MODELES_CLAUDE]
    assert ids[:2] == ["claude-sonnet-5", "haiku"]
    assert all(m["label"] for m in MODELES_CLAUDE)


def _serveur(sessions):
    import threading
    from http.server import ThreadingHTTPServer

    from native.clibridge import bridge

    bridge._Handler.token = "jeton"
    bridge._Handler.sessions = sessions
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), bridge._Handler)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur


def test_pont_chat_diffuse_les_morceaux_et_models_liste():
    import urllib.request

    class _Session:
        def __init__(self):
            self.vus = []

        def repondre(self, messages):
            self.vus.append(messages)
            yield "Oui, "
            yield "je t'entends."

    faux = _Session()
    serveur = _serveur(lambda modele, effort="low": faux)
    base = f"http://127.0.0.1:{serveur.server_address[1]}"
    try:
        req = urllib.request.Request(
            base + "/chat",
            json.dumps({"messages": [{"role": "user", "content": "Tu m'entends ?"}], "model": "haiku"}).encode(),
            {"Authorization": "Bearer jeton", "Content-Type": "application/json"},
        )
        lignes = [json.loads(l) for l in urllib.request.urlopen(req, timeout=5).read().decode().splitlines() if l.strip()]
        assert [l.get("delta") for l in lignes if "delta" in l] == ["Oui, ", "je t'entends."]
        assert lignes[-1] == {"done": True}
        assert faux.vus[0][-1]["content"] == "Tu m'entends ?"

        req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer jeton"})
        modeles = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert [m["id"] for m in modeles["models"]][:2] == ["claude-sonnet-5", "haiku"]

        refus = urllib.request.Request(base + "/models")
        try:
            urllib.request.urlopen(refus, timeout=5)
            raise AssertionError("sans jeton, /models doit refuser")
        except urllib.error.HTTPError as err:
            assert err.code == 401
    finally:
        serveur.shutdown()


def test_cerveau_abonnement_diffuse_et_filtre_le_protocole_outil():
    """Le cerveau distant « abonnement » parle au pont comme un distant d'API."""
    import asyncio

    from src.brain.abonnement import SubscriptionBrain

    class _Session:
        def __init__(self):
            self.vus = []

        def repondre(self, messages):
            self.vus.append(messages)
            yield "Lima, "
            yield "c'est la capitale."

    faux = _Session()
    serveur = _serveur(lambda modele, effort="low": faux)
    url = f"http://127.0.0.1:{serveur.server_address[1]}/ask"

    async def scenario():
        cerveau = SubscriptionBrain(bridge_url=url, token="jeton", model="haiku")
        await cerveau.initialize()
        try:
            sante = await cerveau.health()
            morceaux = [
                c async for c in cerveau.query_streaming(
                    "Capitale du Pérou ?",
                    system="SYS",
                    history=[{"role": "user", "content": "Bonjour"},
                             {"role": "assistant", "content": "Bonjour !"}],
                    tools=[{"type": "function"}],
                )
            ]
        finally:
            await cerveau.close()
        return sante, morceaux

    try:
        sante, morceaux = asyncio.run(scenario())
    finally:
        serveur.shutdown()
    assert sante["ok"] is True
    assert "".join(c["delta"] for c in morceaux) == "Lima, c'est la capitale."
    assert morceaux[0]["ttft_ms"] is not None
    assert morceaux[-1]["stop_reason"] == "stop"
    envoyes = faux.vus[0]
    assert envoyes[0] == {"role": "system", "content": "SYS"}
    assert envoyes[-1] == {"role": "user", "content": "Capitale du Pérou ?"}


def test_la_fabrique_choisit_l_abonnement(monkeypatch):
    from src.brain.abonnement import SubscriptionBrain
    from src.brain.factory import construire_distant

    monkeypatch.setenv("BRAIN_DEEP", "abonnement-claude")
    monkeypatch.setenv("CLI_BRIDGE_URL", "http://host.docker.internal:8766/ask")
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "jeton")
    monkeypatch.setenv("BRAIN_ABONNEMENT_MODEL", "sonnet")
    distant = construire_distant()
    assert isinstance(distant, SubscriptionBrain)
    assert distant.model == "sonnet"
    assert distant.base == "http://host.docker.internal:8766"

    monkeypatch.setenv("BRAIN_DEEP", "abonnement-chatgpt")
    monkeypatch.setenv("CODEX_BRIDGE_URL", "http://host.docker.internal:8765/ask")
    monkeypatch.setenv("BRAIN_ABONNEMENT_MODEL", "gpt-6-luna")
    monkeypatch.setenv("BRAIN_ABONNEMENT_EFFORT", "low")
    chatgpt = construire_distant()
    assert chatgpt.base == "http://host.docker.internal:8765"
    assert (chatgpt.model, chatgpt.effort) == ("gpt-6-luna", "low")

    monkeypatch.setenv("BRAIN_DEEP", "api")
    assert not isinstance(construire_distant(), SubscriptionBrain)


def test_le_host_agent_lit_le_choix_du_distant(tmp_path):
    from dev.scripts.serve_hostagent import charger_env_local

    env_local = tmp_path / ".env.local"
    env_local.write_text(
        "BRAIN_DEEP=abonnement-claude\nBRAIN_ABONNEMENT_MODEL=sonnet\nBRAIN_MODEL=autre\n",
        encoding="utf-8",
    )
    environ = {}
    charger_env_local(chemin=env_local, environ=environ)
    assert environ["BRAIN_DEEP"] == "abonnement-claude"
    assert environ["BRAIN_ABONNEMENT_MODEL"] == "sonnet"
    # La carte figée reste maîtresse des autres clés modèle.
    assert "BRAIN_MODEL" not in environ


def test_initialize_prechauffe_la_session_du_pont():
    """Sans préchauffage, la première phrase paierait ~5 s de démarrage du CLI."""
    import asyncio

    from src.brain.abonnement import SubscriptionBrain

    class _Session:
        def __init__(self):
            self.prechauffes = []

        def prechauffer(self, systeme):
            self.prechauffes.append(systeme)

        def repondre(self, messages):
            yield ""

    faux = _Session()
    serveur = _serveur(lambda modele, effort="low": faux)
    url = f"http://127.0.0.1:{serveur.server_address[1]}/ask"

    async def scenario():
        cerveau = SubscriptionBrain(bridge_url=url, token="jeton", model="haiku")
        await cerveau.initialize()
        await cerveau.close()

    try:
        asyncio.run(scenario())
    finally:
        serveur.shutdown()
    assert len(faux.prechauffes) == 1 and faux.prechauffes[0].strip()


def test_le_cerveau_abonnement_se_declare_sans_outils():
    from src.brain.abonnement import SubscriptionBrain

    assert SubscriptionBrain.supporte_outils is False
