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
import threading
from native import sans_console
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
                  exe=None, model=None, session=None):
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
        # Plus d'--ephemeral : la session est gardée, Presence la rouvre
        # (`codex resume <id>`). --json rend le thread_id (24/09).
        "--json",
        "-C", workdir,
        "-o", out_file,
    ]
    if model:
        cmd += ["-m", model]
    if session:
        cmd += ["resume", session]
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
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **sans_console.options(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    text = Path(out_file).read_text(encoding="utf-8") if Path(out_file).exists() else ""
    return (proc.returncode, text, (stdout or b"").decode("utf-8", errors="replace"),
            (stderr or b"").decode("utf-8", errors="replace"))


# Codex n'admet qu'un écrivain par fil : la console `codex resume <id>` que
# Presence ouvre pour montrer la conversation verrouille la session, et le
# message suivant échouait (« already has an active writer », 25/09).
_VERROU_ECRIVAIN = "already has an active writer"


from native.consoles_presence import consoles_de_session, liberer_session  # noqa: E402,F401


def _fil(sortie):
    for ligne in (sortie or "").splitlines():
        try:
            evenement = json.loads(ligne)
        except ValueError:
            continue
        if isinstance(evenement, dict) and evenement.get("type") == "thread.started":
            return evenement.get("thread_id")
    return None


async def answer_question(question, runner=run_codex, workdir=DEFAULT_WORKDIR,
                          timeout_s=DEFAULT_TIMEOUT_S, session=None,
                          liberer=liberer_session, pause_s=1.0):
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return {"ok": False, "error": "question vide"}
    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "last.txt")
        cmd = build_command(_VOICE_PREFIX + question, workdir=workdir,
                            out_file=out_file, session=session)
        try:
            for essai in range(2):
                resultat = await runner(cmd, out_file, timeout_s)
                code, text = resultat[0], resultat[1]
                sortie = resultat[2] if len(resultat) > 2 else ""
                erreur = resultat[3] if len(resultat) > 3 else ""
                if (code == 0 or essai or not session
                        or _VERROU_ECRIVAIN not in (erreur or "")
                        or not liberer(session)):
                    break
                await asyncio.sleep(pause_s)
        except (asyncio.TimeoutError, TimeoutError):
            return {"ok": False, "error": "delai depasse"}
        except FileNotFoundError:
            return {"ok": False, "error": "codex introuvable"}
    if code != 0:
        return {"ok": False, "error": f"codex a echoue (code {code})"}
    reponse = {"ok": True, "answer": (text or "").strip()}
    fil = _fil(sortie) or session
    if fil:
        reponse["session_id"] = str(fil)
    return reponse


_SESSIONS: dict = {}
_VERROU_SESSIONS = threading.Lock()


def session_pour(modele, effort="low"):
    """Une session de conversation vivante par modèle et effort (mode abonnement)."""
    from native.codexbridge.conversation import SessionCodex

    with _VERROU_SESSIONS:
        cle = (modele, effort)
        if cle not in _SESSIONS:
            _SESSIONS[cle] = SessionCodex(modele=modele, effort=effort)
        return _SESSIONS[cle]


def _chercher_session(requete):
    from native import sessions_harnais as sh

    return sh.chercher(sh.sessions_codex(), requete)


def _dossier_session(session):
    from native import sessions_harnais as sh

    if not session:
        return DEFAULT_WORKDIR
    dossier = sh.cwd_de_session("Codex", session)
    return dossier if dossier and os.path.isdir(dossier) else DEFAULT_WORKDIR


def _modeles():
    """La liste en direct, demandée à l'app-server (`model/list`)."""
    from native.codexbridge.conversation import MODELE_PAR_DEFAUT

    try:
        return session_pour(MODELE_PAR_DEFAUT).modeles()
    except Exception as exc:
        logger.warning(f"model/list : {type(exc).__name__}: {exc}")
        return [{"id": MODELE_PAR_DEFAUT, "label": MODELE_PAR_DEFAUT}]


class _Handler(BaseHTTPRequestHandler):
    sessions = staticmethod(session_pour)

    def _conversation(self):
        from native.codexbridge.conversation import MODELE_PAR_DEFAUT
        from native.conversation_http import servir

        return servir(
            self,
            autorise=lambda entete: authorized(entete, self.token),
            sessions=type(self).sessions,
            modeles=_modeles,
            defaut=MODELE_PAR_DEFAUT,
            catalogue=_chercher_session,
        )

    def do_GET(self):
        if self.path == "/health":
            if not authorized(self.headers.get("Authorization"), self.token):
                return self._send(401, {"ok": False})
            return self._send(200, {"ok": True, "service": "codexbridge", "capability": "conversation"})
        if not self._conversation():
            self._send(501, {"ok": False, "error": "GET non pris en charge"})

    token = ""

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self._conversation():
            return
        if self.path != "/ask":
            return self._send(404, {"ok": False, "error": "inconnu"})
        if not authorized(self.headers.get("Authorization"), self.token):
            return self._send(401, {"ok": False, "error": "non autorise"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "")
            session = payload.get("session") or None
        except Exception:
            return self._send(400, {"ok": False, "error": "requete illisible"})
        self._send(200, asyncio.run(answer_question(
            question, session=session, workdir=_dossier_session(session))))

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
