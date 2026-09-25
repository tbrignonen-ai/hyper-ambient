"""Rejoindre une session de harnais à la voix (24/09).

« Reprends la dernière session Claude », « rejoins la session Codex qui parle
de n8n », « nouvelle session Claude » : décision locale, avant le cerveau,
comme l'annulation. Le pont cherche, MOTHER adopte la session et le dit.
"""
import asyncio

from src.brain.sessions_voix import DemandeSession, demande_de_session, executer, ponts_harnais


def test_derniere_session_nommee():
    assert demande_de_session("Reprends la dernière session Claude.") == DemandeSession(
        "Claude", "derniere", "")


def test_session_qui_parle_de():
    assert demande_de_session("Rejoins la session Codex qui parle de n8n.") == DemandeSession(
        "Codex", "chercher", "n8n")


def test_x_ou_y_dans_le_titre():
    d = demande_de_session("Ouvre la session Claude contenant soutenance ou démo dans le titre")
    assert d == DemandeSession("Claude", "chercher", "soutenance ou démo")


def test_sans_harnais_nomme_on_cherche_partout():
    assert demande_de_session("Retourne dans la session sur le README") == DemandeSession(
        None, "chercher", "le README")


def test_whisper_cloud_code_vaut_claude():
    assert demande_de_session("Reprends la dernière session cloud code").harnais == "Claude"


def test_nouvelle_session():
    assert demande_de_session("Nouvelle session Codex.") == DemandeSession("Codex", "nouvelle", "")
    assert demande_de_session("Démarre une nouvelle session avec Claude").action == "nouvelle"


def test_ce_qui_n_est_pas_une_reprise():
    assert demande_de_session("Demande à Claude d'ouvrir la session de test") is None
    assert demande_de_session("Quelle heure est-il ?") is None
    assert demande_de_session("Reprends depuis le début") is None
    assert demande_de_session(" ".join(["session"] * 30)) is None


class _Pont:
    def __init__(self, trouve):
        self.trouve = trouve
        self.session = "ancienne"
        self.adoptee = None
        self.requetes = []

    async def chercher_session(self, requete):
        self.requetes.append(requete)
        return self.trouve

    def adopter_session(self, session):
        self.adoptee = session
        self.session = session["id"]


def _run(coro):
    return asyncio.run(coro)


def test_reprise_adopte_la_session_et_le_dit():
    pont = _Pont({"id": "c-1", "titre": "SOUTENANCE-TEST", "apercu": "", "score": 0, "date": 5})
    r = _run(executer(DemandeSession("Claude", "derniere", ""), {"Claude": pont}))
    assert pont.adoptee["id"] == "c-1"
    assert (r.harnais, r.session) == ("Claude", "c-1")
    assert "SOUTENANCE-TEST" in r.phrase and "Claude" in r.phrase


def test_sans_titre_l_apercu_est_abrege():
    pont = _Pont({"id": "c-1", "titre": "", "score": 1, "date": 5,
                  "apercu": "Lis le README et dis moi ce qui manque pour la soutenance demain matin"})
    r = _run(executer(DemandeSession("Claude", "chercher", "readme"), {"Claude": pont}))
    assert "Lis le README" in r.phrase
    assert "demain matin" not in r.phrase


def test_sans_harnais_nomme_le_meilleur_des_deux():
    claude = _Pont({"id": "c", "titre": "Voix", "apercu": "", "score": 1, "date": 9})
    codex = _Pont({"id": "x", "titre": "Démo n8n", "apercu": "", "score": 2, "date": 1})
    r = _run(executer(DemandeSession(None, "chercher", "demo n8n"), {"Claude": claude, "Codex": codex}))
    assert r.harnais == "Codex"
    assert claude.adoptee is None


def test_introuvable_ne_change_rien():
    pont = _Pont(None)
    r = _run(executer(DemandeSession("Codex", "chercher", "facturation"), {"Codex": pont}))
    assert r.session is None
    assert pont.session == "ancienne"
    assert "facturation" in r.phrase


def test_nouvelle_session_oublie_la_courante():
    pont = _Pont(None)
    r = _run(executer(DemandeSession("Claude", "nouvelle", ""), {"Claude": pont}))
    assert pont.session is None
    assert r.session is None
    assert "nouvelle" in r.phrase.lower()


def test_harnais_non_branche():
    r = _run(executer(DemandeSession("Codex", "derniere", ""), {"Claude": _Pont(None)}))
    assert "Codex" in r.phrase
    assert r.session is None


def test_les_ponts_se_trouvent_dans_le_registre():
    from src.brain.mandat import RegistreMandats
    from src.brain.tools import ToolRegistry
    from src.brain.tools_cli import register_ask_claude

    registre = ToolRegistry()
    register_ask_claude(registre, token="t", client=object(), registre_mandats=RegistreMandats())
    ponts = ponts_harnais(registre)
    assert list(ponts) == ["Claude"]
    assert hasattr(ponts["Claude"], "chercher_session")


def test_le_host_agent_adopte_et_fait_ouvrir_la_session():
    from types import SimpleNamespace

    from dev.scripts import serve_hostagent

    class _Socket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

    pont = _Pont({"id": "c-1", "titre": "SOUTENANCE-TEST", "apercu": "", "score": 0, "date": 5})
    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = SimpleNamespace(
        get=lambda nom: SimpleNamespace(handler=pont) if nom == "ask_claude" else None
    )
    socket = _Socket()
    phrase = _run(pipeline._rejoindre_session(socket, "Reprends la dernière session Claude"))
    assert "SOUTENANCE-TEST" in phrase
    assert socket.messages == [{"type": "harnais_session", "harnais": "Claude", "session": "c-1"}]


def test_le_host_agent_laisse_passer_le_reste():
    from dev.scripts import serve_hostagent

    pipeline = serve_hostagent.HostPipeline()
    assert _run(pipeline._rejoindre_session(None, "Quelle heure est-il ?")) is None


def test_parler_d_une_session_n_en_reprend_aucune():
    """25/09 : « on va faire une session avec plusieurs tests » a rejoint une
    session Claude au hasard. « va » n'est un verbe de reprise que suivi de
    « dans » ou « sur »."""
    assert demande_de_session(
        "Aujourd'hui on va faire une session avec plusieurs tests. Tu es prête ?") is None
    assert demande_de_session("On passe une bonne session de travail") is None
    assert demande_de_session("Cette session Claude était longue") is None
    assert demande_de_session("Va dans la session Codex").action == "derniere"
    assert demande_de_session("Passe sur la session Claude qui parle de n8n").action == "chercher"
