"""
Pont hote : MOTHER -> Qwen Code CLI (Token Plan).

    GET  /pong|/health
    POST /ask  {"question": "...", "model": "qwen3.6-flash"}
    Authorization: Bearer $QWEN_BRIDGE_TOKEN

Lanes flash J-1 (IDs exacts OG) :
  - deepseek-v4-flash-0731
  - qwen3.6-flash   (defaut pont)
  - qwen3.8-flash   (OK CLI; check plan Personal)

Port 8767. Stdlib only.
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

logger = logging.getLogger("qwenbridge")

DEFAULT_WORKDIR = str(Path(__file__).resolve().parents[2])
DEFAULT_PORT = 8767
DEFAULT_TIMEOUT_S = float(os.environ.get("QWEN_BRIDGE_TIMEOUT_S", "120"))
MAX_QUESTION_CHARS = 4000
DEFAULT_MODEL = os.environ.get("QWEN_BRIDGE_MODEL", "qwen3.8-flash")
ALLOWED_MODELS = {
    "deepseek-v4-flash-0731",
    "deepseek-v4-flash",
    "qwen3.6-flash",
    "qwen3.8-flash",
    "qwen3.8-max",
    "qwen3.8-max-preview",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "deepseek-v4-pro",
}

_VOICE_PREFIX = (
    "Reponds en francais, en deux ou trois phrases parlables, sans code, "
    "sans liste ni markdown. Question : "
)


def build_command(question, workdir=DEFAULT_WORKDIR, exe=None, model=None):
    if exe is None:
        exe = shlex.split(os.environ.get("QWEN_BRIDGE_EXE", "qwen"))
    if not model:
        model = DEFAULT_MODEL
    # Flags valides mesures 20/09 : qwen -y -m MODEL -p PROMPT
    cmd = list(exe) + ["-y", "-m", model, "-p", question]
    _ = workdir
    return cmd


def authorized(header, token):
    if not token:
        return False
    expected = f"Bearer {token}"
    return hmac.compare_digest((header or "").encode(), expected.encode())


async def run_qwen(cmd, out_file, timeout_s, workdir=DEFAULT_WORKDIR):
    env = os.environ.copy()
    env["QWEN_CODE_SUPPRESS_YOLO_WARNING"] = "1"
    cmd = [shutil.which(cmd[0]) or cmd[0]] + list(cmd[1:])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    text = (stdout or b"").decode("utf-8", errors="replace")
    if not text.strip():
        text = (stderr or b"").decode("utf-8", errors="replace")
    Path(out_file).write_text(text, encoding="utf-8")
    return proc.returncode, text.strip()


async def answer_question(question, model=None, runner=run_qwen,
                          workdir=DEFAULT_WORKDIR, timeout_s=DEFAULT_TIMEOUT_S):
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return {"ok": False, "error": "question vide"}
    if not model:
        model = DEFAULT_MODEL
    model = str(model).strip()
    if model not in ALLOWED_MODELS:
        return {"ok": False, "error": f"modele non autorise: {model}"}
    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "last.txt")
        cmd = build_command(_VOICE_PREFIX + question, workdir=workdir, model=model)
        try:
            code, text = await runner(cmd, out_file, timeout_s, workdir=workdir)
        except (asyncio.TimeoutError, TimeoutError):
            return {"ok": False, "error": "delai depasse", "model": model}
        except FileNotFoundError:
            return {"ok": False, "error": "qwen introuvable", "model": model}
    if code != 0:
        return {"ok": False, "error": f"qwen a echoue (code {code})", "model": model}
    return {"ok": True, "answer": (text or "").strip(), "model": model}


class _Handler(BaseHTTPRequestHandler):
    token = ""

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/health", "/pong"):
            return self._send(200, {
                "ok": True,
                "service": "qwenbridge",
                "port": int(os.environ.get("QWEN_BRIDGE_PORT", DEFAULT_PORT)),
                "default_model": DEFAULT_MODEL,
                "lanes": [
                    "deepseek-v4-flash-0731",
                    "qwen3.8-flash",
                    "qwen3.8-max",
                ],
                "allowed": sorted(ALLOWED_MODELS),
            })
        return self._send(404, {"ok": False, "error": "inconnu"})

    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, {"ok": False, "error": "inconnu"})
        if not authorized(self.headers.get("Authorization"), self.token):
            return self._send(401, {"ok": False, "error": "non autorise"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "")
            model = payload.get("model")
        except Exception:
            return self._send(400, {"ok": False, "error": "requete illisible"})
        self._send(200, asyncio.run(answer_question(question, model=model)))

    def log_message(self, fmt, *args):
        logger.info(fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s qwenbridge %(message)s")
    token = os.environ.get("QWEN_BRIDGE_TOKEN", "")
    if not token:
        raise SystemExit("QWEN_BRIDGE_TOKEN absent : le pont reste ferme.")
    host = os.environ.get("QWEN_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("QWEN_BRIDGE_PORT", DEFAULT_PORT))
    _Handler.token = token
    logger.info("ecoute %s:%s defaut=%s", host, port, DEFAULT_MODEL)
    ThreadingHTTPServer((host, port), _Handler).serve_forever()


if __name__ == "__main__":
    main()