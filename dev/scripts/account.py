#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accountability hyper-ambient — circuit ferme.

Regle Thomas 20/09 :
  - tache simple  -> OC seul + ponts (Cursor/Codex/Qwen/Claude), comme hier
  - tache complexe -> a la fin, informer OG ; OG informe OC

Usage:
  account.py open  --lane X --who cursor --complexity simple|complex --out PATH [--exit PATH]
  account.py pulse --lane X
  account.py close --lane X --status done|fail
  account.py scan
  account.py board
  account.py status
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "nights" / "ACCOUNTABILITY-LEDGER.jsonl"
BOARD = ROOT / "nights" / "ACCOUNTABILITY-BOARD.md"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append(ev: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def load_open() -> dict[str, dict]:
    open_l: dict[str, dict] = {}
    if not LEDGER.exists():
        return open_l
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        lane = ev.get("lane")
        if not lane:
            continue
        if ev.get("event") == "open":
            open_l[lane] = ev
        elif ev.get("event") in {"close", "done", "fail"}:
            open_l.pop(lane, None)
        elif ev.get("event") == "pulse" and lane in open_l:
            open_l[lane]["last_pulse"] = ev.get("ts")
    return open_l


def resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def write_board(open_l: dict[str, dict]) -> None:
    lines = [
        "---",
        f"updated: {now()}",
        "type: accountability-board",
        "---",
        "",
        "# ACCOUNTABILITY BOARD",
        "",
        "**Notify :** simple -> OC+ponts | complexe -> OG (puis OG -> OC)",
        "",
        "## Doing",
        "",
    ]
    if not open_l:
        lines.append("_aucune lane ouverte_")
    else:
        lines += [
            "| Lane | Who | Cx | Opened | OUT | EXIT | Notify |",
            "|---|---|---|---|---|---|---|",
        ]
        for lane, ev in sorted(open_l.items()):
            cx = ev.get("complexity", "?")
            notify = "OG->OC" if cx == "complex" else "OC+ponts"
            lines.append(
                f"| `{lane}` | {ev.get('who','?')} | {cx} | {ev.get('ts','')} | "
                f"`{ev.get('out','')}` | `{ev.get('exit_file','')}` | {notify} |"
            )
    lines += ["", "## Regle", "", "- open sans close = fuite", "- complexe: close -> ping OG", ""]
    BOARD.write_text("\n".join(lines), encoding="utf-8")


def cmd_open(a: argparse.Namespace) -> int:
    open_l = load_open()
    if a.lane in open_l:
        print(f"ALREADY_OPEN {a.lane}")
        return 2
    ev = {
        "event": "open",
        "ts": now(),
        "lane": a.lane,
        "who": a.who,
        "complexity": a.complexity,
        "out": a.out,
        "exit_file": a.exit or "",
        "notify": "OG" if a.complexity == "complex" else "OC",
        "note": a.note or "",
    }
    append(ev)
    write_board(load_open())
    print(f"OPEN {a.lane} cx={a.complexity} notify={ev['notify']}")
    return 0


def cmd_pulse(a: argparse.Namespace) -> int:
    if a.lane not in load_open():
        print(f"NOT_OPEN {a.lane}")
        return 2
    append({"event": "pulse", "ts": now(), "lane": a.lane, "note": a.note or ""})
    write_board(load_open())
    print(f"PULSE {a.lane}")
    return 0


def cmd_close(a: argparse.Namespace) -> int:
    open_l = load_open()
    if a.lane not in open_l:
        print(f"NOT_OPEN {a.lane}")
        return 2
    meta = open_l[a.lane]
    status = a.status
    out = resolve(a.out or meta.get("out") or "")
    note = a.note or ""
    if status == "done" and (not out.is_file() or out.stat().st_size == 0):
        status = "fail"
        note = (note + " | OUT manquant/vide").strip(" |")
    notify = "OG" if meta.get("complexity") == "complex" else "OC"
    append(
        {
            "event": "close",
            "ts": now(),
            "lane": a.lane,
            "status": status,
            "notify": notify,
            "note": note,
            "out": str(meta.get("out") or a.out or ""),
        }
    )
    write_board(load_open())
    # Machine-readable hint for OC/OG routing
    print(f"CLOSE {a.lane} status={status} NOTIFY={notify}")
    if notify == "OG":
        print(f"ACTION: SendToAgent OG — lane {a.lane} {status}")
    return 0 if status == "done" else 1


def cmd_scan(_: argparse.Namespace) -> int:
    closed = 0
    for lane, ev in list(load_open().items()):
        ex = ev.get("exit_file") or ""
        if not ex:
            continue
        ep = resolve(ex)
        if not ep.is_file():
            continue
        code = ep.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        code = code[0].strip() if code else ""
        outp = resolve(ev.get("out") or "")
        ok = outp.is_file() and outp.stat().st_size > 0
        status = "done" if code == "0" and ok else "fail"
        notify = "OG" if ev.get("complexity") == "complex" else "OC"
        append(
            {
                "event": "close",
                "ts": now(),
                "lane": lane,
                "status": status,
                "notify": notify,
                "exit_code": code,
                "note": f"scan out_ok={ok}",
                "out": ev.get("out"),
            }
        )
        print(f"AUTO_CLOSE {lane} status={status} NOTIFY={notify} exit={code}")
        if notify == "OG":
            print(f"ACTION: SendToAgent OG — lane {lane} {status}")
        closed += 1
    write_board(load_open())
    print(f"SCAN closed={closed}")
    return 0


def cmd_board(_: argparse.Namespace) -> int:
    write_board(load_open())
    print(BOARD.read_text(encoding="utf-8"))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    open_l = load_open()
    print(json.dumps({"open": list(open_l.keys()), "count": len(open_l)}, ensure_ascii=False))
    return 0 if not open_l else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("open")
    o.add_argument("--lane", required=True)
    o.add_argument("--who", required=True)
    o.add_argument("--complexity", choices=["simple", "complex"], required=True)
    o.add_argument("--out", required=True)
    o.add_argument("--exit", default="")
    o.add_argument("--note", default="")
    o.set_defaults(func=cmd_open)
    p = sp.add_parser("pulse")
    p.add_argument("--lane", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_pulse)
    c = sp.add_parser("close")
    c.add_argument("--lane", required=True)
    c.add_argument("--status", choices=["done", "fail"], required=True)
    c.add_argument("--out", default="")
    c.add_argument("--note", default="")
    c.set_defaults(func=cmd_close)
    s = sp.add_parser("scan")
    s.set_defaults(func=cmd_scan)
    b = sp.add_parser("board")
    b.set_defaults(func=cmd_board)
    st = sp.add_parser("status")
    st.set_defaults(func=cmd_status)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

