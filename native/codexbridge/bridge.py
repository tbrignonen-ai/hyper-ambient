"""
Pont hote : hyper-ambient (conteneur) -> Codex CLI (hote), en lecture seule.

    POST /ask  {"question": "..."}   Authorization: Bearer $CODEX_BRIDGE_TOKEN
    -> {"ok": true, "answer": "..."} | {"ok": false, "error": "..."}

Codex est lance en `codex exec --sandbox read-only` dans le depot : il lit, il
n'ecrit rien. Le pont est ferme sans jeton configure. Stdlib seulement.

    set CODEX_BRIDGE_TOKEN=...   &&   python -m native.codexbridge.bridge
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

logger = logging.getLogger("codexbridge")

DEFAULT_WORKDIR = str(Path(__file__).resolve().parents[2])
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_S = 40.0
MAX_QUESTION_CHARS = 2000

# Consigne de forme : la reponse sera lue a voix haute.
_VOICE_PREFIX = (
    "Reponds en francais, en deux ou trois phrases parlables, sans code, "
    "sans liste ni markdown. Question : "
)


def build_command(question, workdir=DEFAULT_WORKDIR, out_file="last.txt",
                  exe=None, model=None):
    """`exe` : liste d'arguments (ex. `npx -y @openai/codex@0.154.0`), sinon
    $CODEX_BRIDGE_EXE, sinon `codex`. `model` : sinon $CODEX_BRIDGE_MODEL,
    sinon celui de ~/.codex/config.toml."""
    if exe is None:
        exe = shlex.split(os.environ.get("CODEX_BRIDGE_EXE", "codex"))
    if model is None:
        model = os.environ.get("CODEX_BRIDGE_MODEL", "")
    cmd = list(exe) + [
        "exec",
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", workdir,
        "-o", out_file,
    ]
    if model:
        cmd += ["-m", model]
    return cmd + [question]


def authorized(header, token):
    if not token:
        return False
    expected = f"Bearer {token}"
    return hmac.compare_digest((header or "").encode(), expected.encode())


async def run_codex(cmd, out_file, timeout_s):
    cmd = [shutil.which(cmd[0]) or cmd[0]] + list(cmd[1:])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        code = await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    text = Path(out_file).read_text(encoding="utf-8") if Path(out_file).exists() else ""
    return code, text


async def answer_question(question, runner=run_codex, workdir=DEFAULT_WORKDIR,
                          timeout_s=DEFAULT_TIMEOUT_S):
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return {"ok": False, "error": "question vide"}
    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "last.txt")
        cmd = build_command(_VOICE_PREFIX + question, workdir=workdir, out_file=out_file)
        try:
            code, text = await runner(cmd, out_file, timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            return {"ok": False, "error": "delai depasse"}
        except FileNotFoundError:
            return {"ok": False, "error": "codex introuvable"}
    if code != 0:
        return {"ok": False, "error": f"codex a echoue (code {code})"}
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
            question = json.loads(self.rfile.read(length) or b"{}").get("question", "")
        except Exception:
            return self._send(400, {"ok": False, "error": "requete illisible"})
        self._send(200, asyncio.run(answer_question(question)))

    def log_message(self, fmt, *args):
        logger.info(fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s codexbridge %(message)s")
    token = os.environ.get("CODEX_BRIDGE_TOKEN", "")
    if not token:
        raise SystemExit("CODEX_BRIDGE_TOKEN absent : le pont reste ferme.")
    host = os.environ.get("CODEX_BRIDGE_HOST", "0.0.0.0")
    port = int(os.environ.get("CODEX_BRIDGE_PORT", DEFAULT_PORT))
    _Handler.token = token
    logger.info(f"ecoute {host}:{port}, depot {DEFAULT_WORKDIR}, lecture seule")
    ThreadingHTTPServer((host, port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
