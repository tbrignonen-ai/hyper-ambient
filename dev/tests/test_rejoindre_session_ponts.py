"""Le chemin réseau de la reprise de session (24/09).

Le client du host-agent demande au pont `GET /sessions?q=...` ; la session
adoptée part avec les demandes suivantes. Côté Claude, la première demande
dans une session rejointe la *bifurque* (`--fork-session`) : on n'écrit
jamais dans une session que l'utilisateur a peut-être ouverte à côté.
"""
import asyncio
import io
import json

from native.clibridge import bridge as cli
from native.conversation_http import servir


def _run(coro):
    return asyncio.run(coro)


class _Reponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.get_urls = []
        self.posts = []

    async def get(self, url, params=None, headers=None, timeout=None):
        self.get_urls.append((url, params))
        return _Reponse(self.payloads.pop(0))

    async def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append(json)
        return _Reponse(self.payloads.pop(0))


def test_le_client_cherche_sur_le_pont_et_adopte():
    from src.brain.tools_cli import CliBridge

    session = {"id": "c-1", "titre": "T", "apercu": "", "score": 1, "date": 3}
    client = _Client([
        {"ok": True, "session": session},
        {"ok": True, "answer": "Un.", "session_id": "c-2"},
        {"ok": True, "answer": "Deux.", "session_id": "c-2"},
    ])
    pont = CliBridge(token="t", client=client, endpoint="http://h:8766/ask")
    trouve = _run(pont.chercher_session("demo"))
    assert trouve == session
    assert client.get_urls == [("http://h:8766/sessions", {"q": "demo"})]
    pont.adopter_session(trouve)
    _run(pont("q1"))
    _run(pont("q2"))
    # 25/09 : on écrit dans la session rejointe elle-même, comme Codex ;
    # l'utilisateur veut rester dans sa session, pas dans une copie.
    assert client.posts[0]["session"] == "c-1" and "fork" not in client.posts[0]
    assert client.posts[1]["session"] == "c-2" and "fork" not in client.posts[1]


def test_le_client_codex_ne_bifurque_pas():
    from src.brain.tools_codex import CodexBridge

    client = _Client([{"ok": True, "answer": "Un.", "session_id": "x-1"}])
    pont = CodexBridge(token="t", client=client, endpoint="http://h:8765/ask")
    pont.adopter_session({"id": "x-1"})
    _run(pont("q"))
    assert client.posts[0]["session"] == "x-1" and "fork" not in client.posts[0]


def test_pont_injoignable_rien_trouve():
    from src.brain.tools_cli import CliBridge

    class _Casse:
        async def get(self, *a, **k):
            raise OSError("down")

    assert _run(CliBridge(token="t", client=_Casse()).chercher_session("x")) is None


def test_claude_bifurque_sur_demande():
    cmd = cli.build_command("q", exe=["claude"], session="c-1", fourche=True)
    assert cmd[cmd.index("--resume") + 1] == "c-1"
    assert "--fork-session" in cmd
    assert "--fork-session" not in cli.build_command("q", exe=["claude"], session="c-1")


class _Handler:
    def __init__(self, path, token="t"):
        self.command = "GET"
        self.path = path
        self.headers = {"Authorization": f"Bearer {token}"}
        self.envois = []
        self.rfile = io.BytesIO(b"")

    def _send(self, code, payload):
        self.envois.append((code, payload))


def _servir(handler, catalogue):
    return servir(
        handler,
        autorise=lambda e: e == "Bearer t",
        sessions=lambda m, e: None,
        modeles=lambda: [],
        defaut="m",
        catalogue=catalogue,
    )


def test_route_sessions_rend_la_meilleure():
    vu = []

    def catalogue(requete):
        vu.append(requete)
        return {"id": "c-1"}

    h = _Handler("/sessions?q=demo%20n8n")
    assert _servir(h, catalogue)
    assert vu == ["demo n8n"]
    assert h.envois == [(200, {"ok": True, "session": {"id": "c-1"}})]


def test_route_sessions_exige_le_jeton():
    h = _Handler("/sessions?q=x", token="faux")
    assert _servir(h, lambda r: {"id": "c"})
    assert h.envois[0][0] == 401


def test_claude_ferme_la_console_presence_avant_d_ecrire_dans_la_session():
    """25/09 : comme Codex, on écrit dans la session elle-même ; la console
    que Presence a ouverte dessus est fermée d'abord, et rouverte à la réponse."""
    liberees = []

    async def runner(cmd, out_file, timeout_s):
        assert liberees == ["c-1"]
        return 0, '{"result": "Prêt.", "session_id": "c-1"}'

    reponse = _run(cli.answer_question(
        "prêt ?", runner=runner, session="c-1",
        liberer=lambda s: liberees.append(s) or True))
    assert reponse["ok"] is True and reponse.get("session_id") == "c-1"


def test_console_claude_de_presence_reconnue():
    from native.consoles_presence import consoles_de_session

    processus = [
        {"ProcessId": 21, "Name": "conhost.exe",
         "CommandLine": r'conhost.exe C:\npm\claude.cmd --resume c-1 --permission-mode manual'},
        {"ProcessId": 22, "Name": "conhost.exe",
         "CommandLine": r'conhost.exe C:\npm\codex.cmd resume c-1'},
    ]
    assert consoles_de_session(processus, "c-1", "claude") == [21]
    assert consoles_de_session(processus, "c-1", "codex") == [22]
