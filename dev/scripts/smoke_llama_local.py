#!/usr/bin/env python3
"""Ping local llama-server (LFM, alias mother-local) on the Windows host.

    python dev/scripts/smoke_llama_local.py

Probes http://127.0.0.1:8090/v1/models then one short non-streaming
chat completion with model=mother-local.

This script never starts or terminates llama-server. If the port is
down it reports FAIL and exits 2. It must not send any process signal.

IPv4 only: Windows resolves localhost to ::1 first; with mirrored WSL
that loopback does not reach the container.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:8090"
MODELS_URL = HOST + "/v1/models"
CHAT_URL = HOST + "/v1/chat/completions"
ALIAS = "mother-local"
MODELS_TIMEOUT_S = 5.0
CHAT_TIMEOUT_S = 45.0
MAX_TOKENS = 128
PROMPT = "Reponds par un seul mot: ok"

OK, KO, DOWN = "  OK  ", " FAIL ", " DOWN "


def _report(status: str, cap: str, detail: str) -> None:
    print(f"[{status}] {cap:<22} {detail}")


def _get(url: str, timeout: float):
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8", "replace")) if body else {}


def _post(url: str, payload: dict, timeout: float):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8", "replace")) if body else {}


def _model_ids(payload: dict) -> list[str]:
    ids: list[str] = []
    for row in payload.get("data") or []:
        if isinstance(row, dict) and row.get("id"):
            ids.append(str(row["id"]))
    for row in payload.get("models") or []:
        if isinstance(row, dict):
            name = row.get("name") or row.get("id") or row.get("model")
            if name:
                ids.append(str(name))
    return ids


def ping_models() -> tuple[bool, str]:
    t0 = time.perf_counter()
    try:
        status, payload = _get(MODELS_URL, MODELS_TIMEOUT_S)
    except urllib.error.URLError as exc:
        return False, f"unreachable: {exc.reason!s}"
    except TimeoutError:
        return False, "timeout"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    ms = (time.perf_counter() - t0) * 1000
    ids = _model_ids(payload)
    if status != 200:
        return False, f"HTTP {status} in {ms:.0f} ms"
    if ALIAS not in ids and ids and ALIAS not in ids[0]:
        # llama-server sometimes lists the GGUF filename; accept a substring.
        blob = " ".join(ids)
        if ALIAS not in blob and "lfm" not in blob.lower():
            return False, f"alias {ALIAS!r} absent de {ids[:5]!r} ({ms:.0f} ms)"
    shown = ", ".join(ids[:4]) or "(liste vide mais HTTP 200)"
    return True, f"HTTP {status} {shown} - {ms:.0f} ms"


def ping_completion() -> tuple[bool, str]:
    payload = {
        "model": ALIAS,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "stream": False,
    }
    t0 = time.perf_counter()
    try:
        status, body = _post(CHAT_URL, payload, CHAT_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:200]
        return False, f"HTTP {exc.code}: {raw}"
    except urllib.error.URLError as exc:
        return False, f"unreachable: {exc.reason!s}"
    except TimeoutError:
        return False, "timeout"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    ms = (time.perf_counter() - t0) * 1000
    if status != 200:
        return False, f"HTTP {status} in {ms:.0f} ms"
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = (message.get("content") or choice.get("text") or "").strip()
    reasoning = (message.get("reasoning_content") or "").strip()
    stop = choice.get("finish_reason") or "?"
    if not text:
        hint = f" reasoning={reasoning[:60]!r}" if reasoning else ""
        return False, f"reponse vide stop={stop} ({ms:.0f} ms){hint}"
    preview = text.replace("\n", " ")[:80]
    return True, f"{len(text)} chars, stop={stop}, {ms:.0f} ms - {preview!r}"


def main() -> int:
    print("=" * 72)
    print("smoke llama-server  127.0.0.1:8090  alias=mother-local  (LFM)")
    print("never starts or stops the server")
    print("=" * 72)

    models_ok, models_detail = ping_models()
    if not models_ok and models_detail.startswith("unreachable"):
        _report(DOWN, "/v1/models", models_detail)
        _report(DOWN, "completion", "skipped - server not reached")
        print("=" * 72)
        print("0 ok, server unreachable (llama-server left untouched)")
        return 2

    _report(OK if models_ok else KO, "/v1/models", models_detail)

    chat_ok, chat_detail = ping_completion()
    _report(OK if chat_ok else KO, "completion", chat_detail)

    print("=" * 72)
    n_ok = int(models_ok) + int(chat_ok)
    print(f"{n_ok} ok, {2 - n_ok} failed")
    return 0 if models_ok and chat_ok else 1


if __name__ == "__main__":
    sys.exit(main())
