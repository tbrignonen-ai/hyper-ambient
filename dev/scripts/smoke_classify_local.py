#!/usr/bin/env python3
"""Classify REFLEXE/ESCALADE against local llama-server (LFM, mother-local).

    python dev/scripts/smoke_classify_local.py

POSTs the same /completion payload as RouterBrain.classify (GBNF grammar,
prefix cache, n_predict=4) to http://127.0.0.1:8090 — IPv4 only.

3 few-shot REFLEXE + 3 few-shot ESCALADE from CLASSIFY_PREFIX.
Writes latencies to nights/2026-09-02-LFM-CLASSIFY-SMOKE.md.

Never starts or stops llama-server. No process signal. If the port is
down, the report is still written (FAIL) and the process exits 2.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.brain.router import (  # noqa: E402
    CLASSIFY_GRAMMAR,
    CLASSIFY_PREFIX,
    CLASSIFY_SUFFIX,
)

HOST = "http://127.0.0.1:8090"
COMPLETION_URL = HOST + "/completion"
MODELS_URL = HOST + "/v1/models"
ALIAS = "mother-local"
MODELS_TIMEOUT_S = 5.0
CLASSIFY_TIMEOUT_S = 60.0
N_PREDICT = 4

DEFAULT_NIGHTS = Path(
    os.environ.get(
        "NIGHTS_DIR",
        r"C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights",
    )
)
DEFAULT_REPORT = DEFAULT_NIGHTS / "2026-09-02-LFM-CLASSIFY-SMOKE.md"

# Few-shots du prefixe — le smoke mesure le classifieur sur ses propres exemples.
CASES: list[tuple[str, str]] = [
    ("REFLEXE", "Bonjour hyper-ambient."),
    ("REFLEXE", "Merci, c'est noté."),
    ("REFLEXE", "Répète plus fort."),
    ("ESCALADE", "Quelle est la capitale de la Norvège ?"),
    ("ESCALADE", "Il est 14 h 40, ma réunion dure quarante minutes et commence dans vingt minutes, à quelle heure je finis ?"),
    ("ESCALADE", "Quel temps fait-il à Paris demain ?"),
]


def parse_verdict(content: object) -> str:
    """Normalise la reponse native /completion vers REFLEXE | ESCALADE | autre."""
    if content is None:
        return ""
    text = str(content).strip()
    if not text:
        return ""
    first = text.splitlines()[0].strip().strip("\"'`")
    token = first.split()[0] if first.split() else first
    token = token.strip(".,;:").upper()
    if token in {"REFLEXE", "ESCALADE"}:
        return token
    if "REFLEXE" in text.upper() and "ESCALADE" not in text.upper():
        return "REFLEXE"
    if "ESCALADE" in text.upper() and "REFLEXE" not in text.upper():
        return "ESCALADE"
    return token or text[:40]


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


def ping_models() -> tuple[bool, str, float]:
    t0 = time.perf_counter()
    try:
        status, payload = _get(MODELS_URL, MODELS_TIMEOUT_S)
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        return False, f"{type(exc).__name__}: {exc}", ms
    ms = (time.perf_counter() - t0) * 1000
    blob = json.dumps(payload, ensure_ascii=False)
    ok = status == 200 and (ALIAS in blob or "lfm" in blob.lower())
    return ok, f"HTTP {status} ({ms:.0f} ms)", ms


def classify_one(prompt: str) -> dict:
    body = {
        "prompt": CLASSIFY_PREFIX + prompt.strip() + CLASSIFY_SUFFIX,
        "grammar": CLASSIFY_GRAMMAR,
        "n_predict": N_PREDICT,
        "temperature": 0,
        "cache_prompt": True,
    }
    t0 = time.perf_counter()
    try:
        status, payload = _post(COMPLETION_URL, body, CLASSIFY_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        ms = (time.perf_counter() - t0) * 1000
        raw = exc.read().decode("utf-8", "replace")[:240]
        return {
            "ok": False, "verdict": "", "raw": raw,
            "latency_ms": ms, "error": f"HTTP {exc.code}",
            "tokens_predicted": None, "tokens_evaluated": None,
        }
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False, "verdict": "", "raw": "",
            "latency_ms": ms, "error": f"{type(exc).__name__}: {exc}",
            "tokens_predicted": None, "tokens_evaluated": None,
        }
    ms = (time.perf_counter() - t0) * 1000
    raw_content = payload.get("content") if isinstance(payload, dict) else ""
    verdict = parse_verdict(raw_content)
    return {
        "ok": status == 200,
        "verdict": verdict,
        "raw": "" if raw_content is None else str(raw_content),
        "latency_ms": ms,
        "error": "" if status == 200 else f"HTTP {status}",
        "tokens_predicted": payload.get("tokens_predicted") if isinstance(payload, dict) else None,
        "tokens_evaluated": payload.get("tokens_evaluated") if isinstance(payload, dict) else None,
    }


def render_report(rows: list[dict], models_before: tuple, models_after: tuple) -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    n_ok = sum(1 for r in rows if r["match"])
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    cold = latencies[0] if latencies else None
    warm = latencies[1:] if len(latencies) > 1 else []
    lines = [
        "---",
        "date: 2026-09-02",
        "tags: [project/mother, lfm, classify, smoke, cursor-j]",
        "type: rapport",
        "statut: complete",
        "vague: J",
        "---",
        "",
        "# Smoke classify LFM — REFLEXE / ESCALADE",
        "",
        f"Horodatage : {now}",
        f"Endpoint : `{COMPLETION_URL}` (IPv4, alias `{ALIAS}`)",
        f"Grammaire : `{CLASSIFY_GRAMMAR}`",
        f"n_predict : {N_PREDICT} · temperature : 0 · cache_prompt : true",
        "llama-server : **non stoppé**, non démarré. Aucun signal processus.",
        "",
        f"Models avant : {models_before[1]} — {'OK' if models_before[0] else 'FAIL'}",
        f"Models après : {models_after[1]} — {'OK' if models_after[0] else 'FAIL'}",
        "",
        f"Score : **{n_ok}/{len(rows)}** alignés sur le few-shot du préfixe.",
        "",
        "| # | attendu | obtenu | match | latence_ms | tokens_pred | tokens_eval | prompt |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(rows, 1):
        prompt = row["prompt"].replace("|", "\\|")
        if len(prompt) > 80:
            prompt = prompt[:77] + "..."
        match = "oui" if row["match"] else "NON"
        err = row.get("error") or ""
        obtenu = row["verdict"] or (err or "?")
        lines.append(
            f"| {i} | {row['expected']} | {obtenu} | {match} | "
            f"{row['latency_ms']:.0f} | {row.get('tokens_predicted')!s} | "
            f"{row.get('tokens_evaluated')!s} | {prompt} |"
        )
    lines += ["", "## Latences", ""]
    if cold is not None:
        lines.append(
            f"- 1er appel de ce run : **{cold:.0f} ms** "
            "(pas forcément un cache miss : un probe antérieur peut déjà avoir chauffé le préfixe)"
        )
    if warm:
        lines.append(
            f"- suivants : {', '.join(f'{x:.0f} ms' for x in warm)}"
            f" — médiane {sorted(warm)[len(warm)//2]:.0f} ms"
        )
    if latencies:
        lines.append(f"- min {min(latencies):.0f} / max {max(latencies):.0f} / n={len(latencies)}")
    lines += [
        "",
        "## Contrat",
        "",
        "- Même payload que `RouterBrain.classify` (`src/brain/router.py`).",
        "- IPv4 `127.0.0.1` uniquement (piège `localhost` → `::1`).",
        "- Pas de `/v1/chat/completions` : la grammaire GBNF n'existe que sur `/completion`.",
        "- Ce script n'appelle ni `Stop-Process`, ni `taskkill`, ni signal.",
        "",
    ]
    if n_ok == len(rows) and models_before[0] and models_after[0]:
        lines.append("**SMOKE: OK**")
    else:
        lines.append("**SMOKE: FAIL**")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report_path = Path(argv[0]) if argv else DEFAULT_REPORT

    print("=" * 72)
    print(f"smoke classify  {COMPLETION_URL}  alias={ALIAS}")
    print("never starts or stops the server")
    print("=" * 72)

    models_before = ping_models()
    print(f"[ {'OK' if models_before[0] else 'DOWN'} ] /v1/models avant  {models_before[1]}")

    rows: list[dict] = []
    if not models_before[0]:
        for expected, prompt in CASES:
            rows.append({
                "expected": expected,
                "prompt": prompt,
                "verdict": "",
                "match": False,
                "latency_ms": 0.0,
                "error": "server unreachable",
                "tokens_predicted": None,
                "tokens_evaluated": None,
            })
            print(f"[ FAIL ] skipped {expected:<8} {prompt[:50]!r}")
        models_after = models_before
    else:
        for expected, prompt in CASES:
            result = classify_one(prompt)
            match = result["verdict"] == expected and not result["error"]
            row = {
                "expected": expected,
                "prompt": prompt,
                "verdict": result["verdict"],
                "match": match,
                "latency_ms": result["latency_ms"],
                "error": result["error"],
                "tokens_predicted": result["tokens_predicted"],
                "tokens_evaluated": result["tokens_evaluated"],
                "raw": result["raw"],
            }
            rows.append(row)
            tag = "  OK  " if match else " FAIL "
            print(
                f"[{tag}] {expected:<8} got={result['verdict'] or result['error']!r:<12} "
                f"{result['latency_ms']:.0f} ms  {prompt[:48]!r}"
            )
        models_after = ping_models()
        print(f"[ {'OK' if models_after[0] else 'DOWN'} ] /v1/models après  {models_after[1]}")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(rows, models_before, models_after), encoding="utf-8")
    print(f"wrote {report_path}")

    n_ok = sum(1 for r in rows if r["match"])
    print("=" * 72)
    print(f"{n_ok}/{len(rows)} match, llama-server left untouched")
    if not models_before[0]:
        return 2
    return 0 if n_ok == len(rows) and models_after[0] else 1


if __name__ == "__main__":
    sys.exit(main())
