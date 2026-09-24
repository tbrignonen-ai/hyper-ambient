"""Une demande à un harnais vit dans une vraie session, qu'on peut rouvrir.

Séance du 24/09 : « Le détail est dans Claude » était faux — le pont Codex
tournait en `--ephemeral`, le pont Claude ne rendait pas d'identifiant, rien
ne pouvait s'ouvrir. Désormais le pont rend l'identifiant de session, le
client le garde (les demandes suivantes reprennent le même fil) et le mandat
le porte jusqu'à Presence.
"""
import asyncio
import json

from native.clibridge import bridge as cli
from native.codexbridge import bridge as cdx


def _run(coro):
    return asyncio.run(coro)


# -- pont Claude --------------------------------------------------------------

def test_claude_rend_du_json_pour_connaitre_la_session():
    cmd = cli.build_command("q", exe=["claude"])
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--resume" not in cmd


def test_claude_reprend_la_session_donnee():
    cmd = cli.build_command("q", exe=["claude"], session="abc-123")
    assert cmd[cmd.index("--resume") + 1] == "abc-123"
    assert cmd[-1] == "q"


def test_claude_la_reponse_porte_la_session():
    vu = {}

    async def runner(cmd, out_file, timeout_s):
        vu["cmd"] = cmd
        return 0, json.dumps({"result": "Quatre fichiers.", "session_id": "s-1"})

    r = _run(cli.answer_question("q", runner=runner, session="s-0"))
    assert r == {"ok": True, "answer": "Quatre fichiers.", "session_id": "s-1"}
    assert vu["cmd"][vu["cmd"].index("--resume") + 1] == "s-0"


def test_claude_texte_brut_reste_accepte():
    async def runner(cmd, out_file, timeout_s):
        return 0, "Quatre fichiers."

    assert _run(cli.answer_question("q", runner=runner)) == {
        "ok": True, "answer": "Quatre fichiers."}


# -- pont Codex ---------------------------------------------------------------

def test_codex_n_est_plus_ephemere_et_parle_en_json():
    cmd = cdx.build_command("q", out_file="o.txt")
    assert "--ephemeral" not in cmd
    assert "--json" in cmd
    assert "resume" not in cmd


def test_codex_reprend_la_session_apres_les_options():
    cmd = cdx.build_command("q", out_file="o.txt", session="th-9")
    i = cmd.index("resume")
    assert cmd[i + 1:] == ["th-9", "q"]
    assert cmd.index("--sandbox") < i
    assert "-C" not in cmd[i:]


def test_codex_la_reponse_porte_le_fil():
    sortie = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "th-1"}),
        json.dumps({"type": "turn.completed"}),
    ])

    async def runner(cmd, out_file, timeout_s):
        return 0, "Fait.", sortie

    r = _run(cdx.answer_question("q", runner=runner))
    assert r == {"ok": True, "answer": "Fait.", "session_id": "th-1"}


def test_codex_la_reprise_garde_le_fil_meme_sans_evenement():
    async def runner(cmd, out_file, timeout_s):
        return 0, "Fait."

    r = _run(cdx.answer_question("q", runner=runner, session="th-2"))
    assert r["session_id"] == "th-2"


# -- client côté host-agent ---------------------------------------------------

class _Reponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.envois = []

    async def post(self, url, json=None, headers=None, timeout=None):
        self.envois.append(json)
        return _Reponse(self.payloads.pop(0))


def test_le_client_garde_la_session_et_la_reprend():
    from src.brain.tools_cli import CliBridge

    client = _Client([
        {"ok": True, "answer": "Un.", "session_id": "s-1"},
        {"ok": True, "answer": "Deux.", "session_id": "s-1"},
    ])
    pont = CliBridge(token="t", client=client)
    assert _run(pont("q1")) == "Un."
    assert pont.session == "s-1"
    _run(pont("q2"))
    assert "session" not in client.envois[0]
    assert client.envois[1]["session"] == "s-1"


def test_le_client_codex_garde_aussi_la_session():
    from src.brain.tools_codex import CodexBridge

    client = _Client([{"ok": True, "answer": "Un.", "session_id": "th-1"}])
    pont = CodexBridge(token="t", client=client)
    _run(pont("q1"))
    assert pont.session == "th-1"


def test_le_mandat_porte_la_session_du_pont():
    from src.brain.mandat import RegistreMandats, confier

    class Pont:
        session = None

        async def __call__(self, question):
            self.session = "s-7"
            return "Réponse."

    async def scenario():
        registre = RegistreMandats()
        mandat = await confier(registre, "Claude", "lis le README", "README", Pont())
        await mandat.tache
        return mandat

    assert _run(scenario()).session == "s-7"
