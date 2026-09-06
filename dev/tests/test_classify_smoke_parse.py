"""Parse du smoke classify — hors llama-server, hors socket."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CHEMIN = RACINE / "dev" / "scripts" / "smoke_classify_local.py"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_classify_local", CHEMIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load()


def test_cases_sont_trois_plus_trois():
    attendus = [c[0] for c in smoke.CASES]
    assert attendus.count("REFLEXE") == 3
    assert attendus.count("ESCALADE") == 3
    assert len(smoke.CASES) == 6


def test_cases_sont_les_few_shots_du_prefixe():
    from src.brain.router import CLASSIFY_PREFIX

    for _label, prompt in smoke.CASES:
        assert prompt in CLASSIFY_PREFIX


def test_parse_verdict_strip_et_cas():
    assert smoke.parse_verdict("REFLEXE") == "REFLEXE"
    assert smoke.parse_verdict(" REFLEXE\n") == "REFLEXE"
    assert smoke.parse_verdict("escalade") == "ESCALADE"
    assert smoke.parse_verdict('"ESCALADE"') == "ESCALADE"
    assert smoke.parse_verdict("") == ""
    assert smoke.parse_verdict(None) == ""


def test_parse_verdict_bruit_autour():
    assert smoke.parse_verdict("REFLEXE.") == "REFLEXE"
    assert smoke.parse_verdict("FAST") == "FAST"
    assert smoke.parse_verdict("hello REFLEXE") == "REFLEXE"


def test_payload_constantes_alignent_le_routeur():
    from src.brain.router import CLASSIFY_GRAMMAR

    assert smoke.CLASSIFY_GRAMMAR == CLASSIFY_GRAMMAR
    assert smoke.HOST == "http://127.0.0.1:8090"
    assert smoke.COMPLETION_URL.endswith("/completion")
    assert smoke.N_PREDICT == 4
    assert "localhost" not in smoke.HOST
    assert smoke.ALIAS == "mother-local"


def test_render_report_contient_score_et_invariants():
    rows = [
        {
            "expected": "REFLEXE",
            "prompt": "Bonjour hyper-ambient.",
            "verdict": "REFLEXE",
            "match": True,
            "latency_ms": 90.2,
            "tokens_predicted": 4,
            "tokens_evaluated": 200,
            "error": "",
        }
    ]
    md = smoke.render_report(rows, (True, "HTTP 200 (12 ms)"), (True, "HTTP 200 (8 ms)"))
    assert "1/1" in md
    assert "SMOKE: OK" in md
    assert "non stoppé" in md or "non stoppe" in md.replace("é", "e")
    assert "/completion" in md
    assert "127.0.0.1" in md
