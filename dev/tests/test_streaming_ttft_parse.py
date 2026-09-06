"""Tests de parsing offline d'une réponse SSE streaming et calcul du TTFT (Time to First Token).

Zéro socket, zéro réseau réel, zéro dépendance à llama-server.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def parse_sse_events(raw_sse_text: str) -> List[Dict[str, Any]]:
    """Parse a stream of Server-Sent Events into a list of JSON data payloads."""
    events: List[Dict[str, Any]] = []
    for line in raw_sse_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                payload = json.loads(data_str)
                events.append(payload)
            except json.JSONDecodeError:
                continue
    return events


def extract_first_token_and_ttft(
    events: List[Dict[str, Any]],
    request_start_time: float,
    timestamps: Optional[List[float]] = None
) -> Tuple[Optional[str], Optional[float], str]:
    """
    Extrait le premier token textuel non-vide et calcule l'intervalle jusqu'au premier token.
    
    Retourne: (premier_token, ttft_ms, full_text)
    """
    first_token: Optional[str] = None
    ttft_ms: Optional[float] = None
    text_parts: List[str] = []
    
    for idx, ev in enumerate(events):
        chunk_text = ""
        # Format /completion llama.cpp
        if "content" in ev and isinstance(ev["content"], str):
            chunk_text = ev["content"]
        # Format /v1/chat/completions OpenAI compat
        elif "choices" in ev and isinstance(ev["choices"], list) and len(ev["choices"]) > 0:
            delta = ev["choices"][0].get("delta", {})
            chunk_text = delta.get("content") or delta.get("reasoning_content") or ""
        
        if chunk_text:
            text_parts.append(chunk_text)
            if first_token is None:
                first_token = chunk_text
                if timestamps is not None and idx < len(timestamps):
                    ttft_ms = (timestamps[idx] - request_start_time) * 1000.0

    full_text = "".join(text_parts)
    return first_token, ttft_ms, full_text


def test_parse_sse_events_standard():
    raw_sse = (
        'data: {"id":"1","choices":[{"delta":{"content":"Bonjour"}}]}\n\n'
        'data: {"id":"2","choices":[{"delta":{"content":" monde"}}]}\n\n'
        'data: [DONE]\n'
    )
    events = parse_sse_events(raw_sse)
    assert len(events) == 2
    assert events[0]["choices"][0]["delta"]["content"] == "Bonjour"
    assert events[1]["choices"][0]["delta"]["content"] == " monde"


def test_parse_sse_events_with_corrupt_lines_and_spaces():
    raw_sse = (
        ': ping comment\n'
        'data: invalid json\n'
        'data: {"content":"REF"}\n'
        '\n'
        '   \n'
        'data: {"content":"LEXE"}\n'
        'data: [DONE]\n'
        'data: {"content":"IGNORED"}\n'
    )
    events = parse_sse_events(raw_sse)
    assert len(events) == 2
    assert events[0]["content"] == "REF"
    assert events[1]["content"] == "LEXE"


def test_extract_first_token_chat_completions():
    events = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "REFLEXE"}}]},
        {"choices": [{"delta": {"content": ""}}]},
    ]
    req_t0 = 100.0
    timestamps = [100.010, 100.025, 100.030]
    
    first_token, ttft_ms, full = extract_first_token_and_ttft(events, req_t0, timestamps)
    assert first_token == "REFLEXE"
    assert ttft_ms is not None
    assert round(ttft_ms, 2) == 25.0
    assert full == "REFLEXE"


def test_extract_first_token_completion_native():
    events = [
        {"content": ""},
        {"content": "ESCALADE"},
        {"content": "\n"},
    ]
    req_t0 = 50.0
    timestamps = [50.010, 50.032, 50.040]
    
    first_token, ttft_ms, full = extract_first_token_and_ttft(events, req_t0, timestamps)
    assert first_token == "ESCALADE"
    assert ttft_ms is not None
    assert round(ttft_ms, 2) == 32.0
    assert full == "ESCALADE\n"


def test_extract_first_token_with_reasoning_delta():
    # LFM2.5 peut émettre reasoning_content avant content
    events = [
        {"choices": [{"delta": {"reasoning_content": "Pensée..."}}]},
        {"choices": [{"delta": {"content": "Réponse"}}]},
    ]
    req_t0 = 0.0
    timestamps = [0.015, 0.040]
    first_token, ttft_ms, full = extract_first_token_and_ttft(events, req_t0, timestamps)
    assert first_token == "Pensée..."
    assert ttft_ms == 15.0
    assert full == "Pensée...Réponse"


def test_extract_first_token_empty_stream():
    events = []
    first_token, ttft_ms, full = extract_first_token_and_ttft(events, 0.0, [])
    assert first_token is None
    assert ttft_ms is None
    assert full == ""
