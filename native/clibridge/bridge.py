"""
Pont hote : MOTHER (conteneur) -> Claude CLI / Hermes CLI (hote), lecture seule.

    POST /ask  {"question": "...", "agent": "claude"|"hermes"}
    Authorization: Bearer $CLI_BRIDGE_TOKEN
    -> {"ok": true, "answer": "..."} | {"ok": false, "error": "..."}

Claude est lance en `claude -p --restricted --permission-mode plan` dans le
depot : il lit, il n'ecrit rien. Hermes a une ligne de commande declaree, mais
le pont refuse de le lancer tant que `CLI_BRIDGE_HERMES=1` n'arme pas le
chemin (un binaire present ne suffit pas).
Le pont est ferme sans jeton configure. Stdlib seulement.

    set CLI_BRIDGE_TOKEN=...   &&   python -m native.clibridge.bridge
"""
import asyncio
import hmac
import json
import logging
import os
import shlex
import shutil
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger("clibridge")

DEFAULT_WORKDIR = str(Path(__file__).resolve().parents[2])
DEFAULT_PORT = 8766
# 90 s, et non 40. Mesure du 13 septembre : Claude rend un fichier en 9,9 s
# mais depasse 40 s des qu'on lui demande une analyse d'architecture — c'est-a-dire
# exactement ce pour quoi `ask_claude` existe. Le delai etait fige en dur ; il se
# regle desormais sans toucher au code, parce que la bonne valeur depend de la
# question et de la machine, pas du fichier.
DEFAULT_TIMEOUT_S = float(os.environ.get("CLI_BRIDGE_TIMEOUT_S", "90"))
MAX_QUESTION_CHARS = 2000

# Consigne de forme : la reponse sera lue a voix haute.
_VOICE_PREFIX = (
    "Reponds en francais, en deux ou trois phrases parlables, sans code, "
    "sans liste ni markdown. Question : "
)

# Table de construction : l'executable change, le contrat (print, pas de
# bypass) ne change pas. Hermes : chemin ecrit, pas emprunte sans armement.
_AGENTS = {
    "claude": {
        "exe_env": "CLI_BRIDGE_CLAUDE_EXE",
        "default_exe": "claude",
        "missing": "claude introuvable",
        "failed": "claude a echoue",
    },
    "hermes": {
        "exe_env": "CLI_BRIDGE_HERMES_EXE",
        "default_exe": "hermes",
        "missing": "hermes indisponible",
        "failed": "hermes a echoue",
    },
}


def _exe_for(agent, exe=None):
    spec = _AGENTS[agent]
    if exe is None:
        exe = shlex.split(os.environ.get(spec["exe_env"], spec["default_exe"]))
    return list(exe)


def build_command(question, agent="claude", workdir=DEFAULT_WORKDIR, exe=None,
                  model=None):
    """`agent` choisit l'argv. `exe` : liste d'arguments, sinon $CLI_BRIDGE_*_EXE,
    sinon le nom court. `workdir` est le cwd du processus (voir run_cli), pas
    un flag dangereux."""
    _ = workdir
    if agent not in _AGENTS:
        raise ValueError(f"agent inconnu: {agent}")
    if model is None:
        model = os.environ.get("CLI_BRIDGE_MODEL", "")
    cmd = _exe_for(agent, exe)
    if agent == "claude":
        cmd += [
            "-p",
            "--output-format", "text",
            "--restricted",
            "--permission-mode", "plan",
            "--permission-prompts", "none",
        ]
    else:
        # Hermes : meme geste print. Pas de flag dangereux. Pas de processus
        # tant que lookup() dit absent — voir answer_question.
        cmd += ["-p"]
    if model:
        cmd += ["--model", model]
    return cmd + [question]


def authorized(header, token):
    if not token:
        return False
    expected = f"Bearer {token}"
    return hmac.compare_digest((header or "").encode(), expected.encode())


async def run_cli(cmd, out_file, timeout_s, workdir=DEFAULT_WORKDIR):
    cmd = [shutil.which(cmd[0]) or cmd[0]] + list(cmd[1:])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=workdir,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    text = (stdout or b"").decode("utf-8", errors="replace")
    Path(out_file).write_text(text, encoding="utf-8")
    return proc.returncode, text.strip()


async def answer_question(question, runner=run_cli, workdir=DEFAULT_WORKDIR,
                          timeout_s=DEFAULT_TIMEOUT_S, agent="claude",
                          lookup=shutil.which):
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return {"ok": False, "error": "question vide"}
    agent = (agent or "claude").strip().lower()
    if agent not in _AGENTS:
        return {"ok": False, "error": "agent inconnu"}
    spec = _AGENTS[agent]
    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "last.txt")
        cmd = build_command(
            _VOICE_PREFIX + question, agent=agent, workdir=workdir
        )
        # Hermes : chemin declare, processus refuse tant que CLI_BRIDGE_HERMES=1
        # n'arme pas explicitement. Un binaire present ne suffit pas.
        if agent == "hermes" and (
            os.environ.get("CLI_BRIDGE_HERMES", "").strip().lower()
            not in {"1", "true", "yes", "on"}
            or not lookup(cmd[0])
        ):
            return {"ok": False, "error": spec["missing"]}
        try:
            code, text = await runner(cmd, out_file, timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            return {"ok": False, "error": "delai depasse"}
        except FileNotFoundError:
            return {"ok": False, "error": spec["missing"] if agent == "hermes"
                    else "claude introuvable"}
    if code != 0:
        return {"ok": False, "error": f"{agent} a echoue (code {code})"}
    return {"ok": True, "answer": (text or "").strip()}


class _Handler(BaseHTTPRequestHandler):
    token = ""

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, {"ok": False, "error": "inconnu"})
        if not authorized(self.headers.get("Authorization"), self.token):
            return self._send(401, {"ok": False, "error": "non autorise"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "")
            agent = payload.get("agent", "claude")
        except Exception:
            return self._send(400, {"ok": False, "error": "requete illisible"})
        self._send(200, asyncio.run(answer_question(question, agent=agent)))

    def log_message(self, fmt, *args):
        logger.info(fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s clibridge %(message)s")
    token = os.environ.get("CLI_BRIDGE_TOKEN", "")
    if not token:
        raise SystemExit("CLI_BRIDGE_TOKEN absent : le pont reste ferme.")
    host = os.environ.get("CLI_BRIDGE_HOST", "0.0.0.0")
    port = int(os.environ.get("CLI_BRIDGE_PORT", DEFAULT_PORT))
    _Handler.token = token
    logger.info(f"ecoute {host}:{port}, depot {DEFAULT_WORKDIR}, lecture seule")
    ThreadingHTTPServer((host, port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
