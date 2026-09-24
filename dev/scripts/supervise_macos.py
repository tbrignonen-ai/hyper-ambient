"""Lanceur DEV macOS : uniquement les processus qu'il possède, ports locaux."""
from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dev.scripts.preflight_macos import inspect, read_env  # noqa: E402
from native.macos.profile import apply, model_path, paths, require_platform  # noqa: E402


def port_busy(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def json_get(url: str, token: str | None = None) -> dict | None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=1.0) as response:
            return json.load(response)
    except Exception:
        return None


def wait_ready(proc, probe, timeout: float, label: str) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if proc.poll() is not None:
            raise RuntimeError(f"{label} s'est arrêté avant readiness (code {proc.returncode})")
        if probe():
            return
        time.sleep(0.5)
    raise TimeoutError(f"{label} n'est pas prêt après {timeout:.0f} s")


def start(cmd, env, log_dir: Path, label: str):
    with (log_dir / f"{label}.log").open("ab") as output:
        return subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)


def stop_owned(children):
    for proc in reversed(children):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for proc in reversed(children):
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=3)


def run(config: Path) -> int:
    require_platform()
    def _sigterm(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _sigterm)
    result = inspect(config, dry_run=False)
    failing = [name for name, check in result["checks"].items() if check["status"] == "FAIL"]
    if failing:
        print("Préflight bloquant : " + ", ".join(failing), file=sys.stderr)
        return 1
    env = dict(os.environ)
    env.update(read_env(config))
    apply(env)
    env["HOSTAGENT_HOST"] = "127.0.0.1"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    home = Path.home()
    cli_dirs = ["/opt/homebrew/bin", "/usr/local/bin", str(home / ".local/bin"),
                str(home / ".npm-global/bin")]
    cli_dirs.extend(str(p) for p in sorted((home / ".nvm/versions/node").glob("*/bin"), reverse=True))
    env["PATH"] = os.pathsep.join(cli_dirs + [env.get("PATH", "/usr/bin:/bin")])
    log_dir = paths(env)["logs"]
    log_dir.mkdir(parents=True, exist_ok=True)
    lock = log_dir / "mac-16g-voix-max.pid"
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="ascii"))
            os.kill(pid, 0)
        except (ValueError, ProcessLookupError):
            lock.unlink()
        else:
            raise RuntimeError(f"MOTHER Mac déjà lancé (PID {pid})")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(str(os.getpid()))
    children = []
    try:
        for port in (8080, 8001):
            if port_busy(port):
                raise RuntimeError(f"Port {port} déjà occupé : identité du service non garantie")
        text_path = model_path("text", env)
        text_proc = start([sys.executable, "-m", "native.macos.text_server", "--model", str(text_path),
                           "--host", "127.0.0.1", "--port", "8080",
                           "--max-tokens", "256", "--decode-concurrency", "1",
                           "--prompt-concurrency", "1", "--prompt-cache-size", "1",
                           "--prompt-cache-bytes", "268435456"], env, log_dir, "mlx-text")
        children.append(text_proc)
        wait_ready(text_proc, lambda: any(
            str(item.get("id", "")) in {str(text_path), text_path.name}
            for item in (json_get("http://127.0.0.1:8080/v1/models") or {}).get("data", [])),
            120, "Texte MLX")
        local = read_env(ROOT / ".env.local")
        for label, port, module, token_key, cli, service in (
            ("codex", 8765, "native.codexbridge.bridge", "CODEX_BRIDGE_TOKEN", "codex", "codexbridge"),
            ("claude", 8766, "native.clibridge.bridge", "CLI_BRIDGE_TOKEN", "claude", "clibridge"),
        ):
            token = local.get(token_key) or env.get(token_key)
            if not token or not shutil.which(cli, path=env["PATH"]):
                continue
            if port_busy(port):
                raise RuntimeError(f"Port {port} déjà occupé avant lancement du pont {label}")
            child_env = dict(env)
            child_env[token_key] = token
            child_env["CODEX_BRIDGE_HOST" if label == "codex" else "CLI_BRIDGE_HOST"] = "127.0.0.1"
            proc = start([sys.executable, "-m", module], child_env, log_dir, "pont-" + label)
            children.append(proc)
            wait_ready(proc, lambda p=port, t=token, s=service:
                       (json_get(f"http://127.0.0.1:{p}/health", t) or {}).get("service") == s,
                       15, "Pont " + label)
        host = start([sys.executable, "-u", str(ROOT / "dev/scripts/serve_hostagent.py")], env,
                     log_dir, "hostagent")
        children.append(host)
        wait_ready(host, lambda: json_get("http://127.0.0.1:8001/") ==
                   {"status": "ready", "transport": "hostagent"}, 180, "Host-agent")
        print("MOTHER Mac prêt ; ouverture de Presence. Journaux :", log_dir, flush=True)
        presence = subprocess.Popen([sys.executable, "-u", str(ROOT / "native/presence/app.py")],
                                    cwd=ROOT, env=env, start_new_session=True)
        children.append(presence)
        return presence.wait()
    finally:
        stop_owned(children)
        if lock.exists() and lock.read_text(encoding="ascii").strip() == str(os.getpid()):
            lock.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "packaging/macos/mac-16g.env.example")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        result = inspect(args.config, dry_run=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result["status"] == "FAIL")
    try:
        return run(args.config)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
