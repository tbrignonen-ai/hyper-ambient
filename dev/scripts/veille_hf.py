"""Veille Hugging Face par API publique — oreille / voix / cerveau locaux.

Stdlib uniquement. Relançable chaque nuit. Aucun téléchargement de poids.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

API_MODELS = "https://huggingface.co/api/models"
USER_AGENT = "hyper-ambient-veille-hf/1.0 (stdlib; no-token)"
WINDOW_DAYS = 120
PRIORITY_DAYS = 30
LIMIT = 100
EXPAND_FIELDS = (
    "createdAt",
    "lastModified",
    "likes",
    "downloads",
    "library_name",
    "tags",
    "safetensors",
    "gguf",
    "cardData",
)
MAX_ASR_PARAMS = 2_000_000_000
MAX_DENSE_LLM_PARAMS = 9_000_000_000
MAX_Q4_BYTES = 6 * 1024**3
MAX_TTS_VRAM_BYTES = 2 * 1024**3
Q4_BYTES_PER_PARAM = 0.6
FP16_BYTES_PER_PARAM = 2.0
SLEEP_S = 0.35

REFERENCE_NEEDLES = {
    "asr": (
        "whisper-large-v3-turbo",
        "qwen3-asr",
        "parakeet-tdt-0.6b-v3",
        "parakeet tdt 0.6b v3",
        "stt-1b-en_fr",
    ),
    "tts": (
        "supertonic-3",
        "piper",
    ),
    "llm": (
        "luciole-8b",
        "ministral-3-8b",
        "qwen3.5-4b",
        "qwen3.5-4b",
    ),
}
REFERENCE_SEARCHES = {
    "asr": (
        "whisper-large-v3-turbo",
        "Qwen3-ASR",
        "Parakeet TDT 0.6B v3",
        "stt-1b-en_fr",
    ),
    "tts": (
        "Supertonic-3",
        "Piper fr",
    ),
    "llm": (
        "Luciole-8B",
        "Ministral-3-8B",
        "Qwen3.5-4B",
    ),
}
AUDIO_AUTHORS = (
    "openai",
    "Qwen",
    "nvidia",
    "microsoft",
    "google",
    "facebook",
    "mistralai",
    "kyutai",
    "hexgrad",
    "k2-fsa",
    "FunAudioLLM",
    "stepfun-ai",
    "tencent",
    "ResembleAI",
    "neuphonic",
    "Supertone",
    "rhasspy",
    "coqui",
    "myshell-ai",
    "fishaudio",
    "sesame",
    "canopylabs",
    "OpenBMB",
    "IndexTeam",
    "Edge0",
)
LLM_AUTHORS = (
    "Qwen",
    "google",
    "mistralai",
    "meta-llama",
    "microsoft",
    "ibm-granite",
    "LiquidAI",
    "allenai",
    "HuggingFaceTB",
    "openbmb",
    "deepseek-ai",
    "zai-org",
    "nvidia",
    "tencent",
    "baidu",
    "CohereLabs",
    "swiss-ai",
    "utter-project",
    "OpenLLM-France",
)
CPU_FORMATS = frozenset({"gguf", "onnx", "ctranslate2"})
FR_TAGS = frozenset({"fr", "fra", "french", "fr-fr", "fr_fr", "francais", "français"})
FR_LANGS = frozenset({"fr", "fra", "french", "fr-fr", "fr_fr", "francais", "français"})
NEMO_MARKERS = frozenset({"nemo", "nemo_toolkit", "nvidia-nemo"})
RUST_MARKERS = frozenset({"rust", "candle", "ort-rust"})
STREAM_MARKERS = ("stream", "realtime", "real-time", "real_time")
TOOL_MARKERS = ("tool-calling", "function-calling", "tools", "tool_call", "function_call")
MOE_MARKERS = ("moe", "mixture-of-experts", "mixture_of_experts")


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def last_activity(model: dict[str, Any]) -> datetime | None:
    dates = [_as_dt(model.get("lastModified")), _as_dt(model.get("createdAt"))]
    present = [d for d in dates if d is not None]
    return max(present) if present else None


def in_date_window(model: dict[str, Any], now: datetime, days: int = WINDOW_DAYS) -> bool:
    created = _as_dt(model.get("createdAt"))
    modified = _as_dt(model.get("lastModified"))
    cutoff = now - timedelta(days=days)
    return bool((created and created >= cutoff) or (modified and modified >= cutoff))


def is_priority_window(model: dict[str, Any], now: datetime, days: int = PRIORITY_DAYS) -> bool:
    return in_date_window(model, now, days=days)


def _total_from(blob: Any) -> int | None:
    if not isinstance(blob, dict):
        return None
    total = blob.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return None
    return int(total)


def param_count(model: dict[str, Any]) -> int | None:
    n = _total_from(model.get("safetensors"))
    if n is not None:
        return n
    return _total_from(model.get("gguf"))


def q4_bytes_estimate(params: int) -> float:
    return params * Q4_BYTES_PER_PARAM


def _norm(text: str) -> str:
    return text.casefold().replace("_", "-")


def _tags(model: dict[str, Any]) -> list[str]:
    tags = model.get("tags") or []
    return [str(t) for t in tags]


def _card(model: dict[str, Any]) -> dict[str, Any]:
    card = model.get("cardData")
    return card if isinstance(card, dict) else {}


def _card_languages(card: dict[str, Any]) -> list[str]:
    raw = card.get("language") or card.get("languages") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def french_proof(model: dict[str, Any]) -> str:
    for tag in _tags(model):
        if tag.casefold() in FR_TAGS:
            return f"tag `{tag}`"
    card = _card(model)
    for lang in _card_languages(card):
        if lang.casefold() in FR_LANGS:
            return f"cardData.language=`{lang}`"
    ident = str(model.get("id") or "")
    ident_n = _norm(ident)
    if any(tok in ident_n.split("/")[-1].replace(".", "-").split("-") for tok in ("fr", "fra", "french")):
        return f"id `{ident}`"
    if "en-fr" in ident_n or "en_fr" in ident_n.replace("-", "_") or "en-fr" in ident_n:
        return f"id `{ident}` (en_fr)"
    return "[À VÉRIFIER] pas de preuve FR dans l'API"


def has_french(model: dict[str, Any]) -> bool:
    return not french_proof(model).startswith("[À VÉRIFIER]")


def multilingual_declared(model: dict[str, Any]) -> str:
    for tag in _tags(model):
        if tag.casefold() in FR_TAGS:
            return f"tag `{tag}`"
    langs = _card_languages(_card(model))
    if langs:
        shown = ", ".join(langs[:12])
        suffix = "…" if len(langs) > 12 else ""
        return f"cardData.language=`{shown}{suffix}`"
    for tag in _tags(model):
        if "multilingual" in tag.casefold() or tag.casefold() in {"multi-lingual", "multilingue"}:
            return f"tag `{tag}`"
    card = _card(model)
    for value in card.values():
        if isinstance(value, str) and "multilingual" in value.casefold():
            return "cardData mention `multilingual`"
        if isinstance(value, list) and any(
            isinstance(x, str) and "multilingual" in x.casefold() for x in value
        ):
            return "cardData mention `multilingual`"
    ident = str(model.get("id") or "")
    if "multilingual" in ident.casefold():
        return f"id `{ident}`"
    return "[À VÉRIFIER]"


def available_formats(model: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    if isinstance(model.get("safetensors"), dict):
        found.add("safetensors")
    if isinstance(model.get("gguf"), dict):
        found.add("gguf")
    lib = str(model.get("library_name") or "").casefold()
    if lib in {"gguf", "onnx", "onnxruntime", "ctranslate2", "safetensors"}:
        found.add("onnx" if lib == "onnxruntime" else lib)
    for tag in _tags(model):
        t = tag.casefold()
        if t in {"gguf", "onnx", "ctranslate2", "safetensors"}:
            found.add(t)
        if "gguf" in t:
            found.add("gguf")
        if t == "onnx" or t.endswith("-onnx") or "onnx" == t:
            found.add("onnx")
        if "ctranslate2" in t or t == "ct2":
            found.add("ctranslate2")
    return sorted(found)


def windows_native(formats: list[str], tags: list[str], library_name: str | None) -> str:
    fmt = {f.casefold() for f in formats}
    if fmt & CPU_FORMATS:
        return "oui probable"
    markers = {t.casefold() for t in tags}
    lib = (library_name or "").casefold()
    markers.add(lib)
    if markers & NEMO_MARKERS or markers & RUST_MARKERS:
        return "à vérifier"
    if lib in {"nemo", "nemo_toolkit"} or "nemo" in lib:
        return "à vérifier"
    if "rust" in lib or lib == "candle":
        return "à vérifier"
    return "à vérifier"


def license_of(model: dict[str, Any]) -> str:
    card = _card(model)
    lic = card.get("license") or model.get("license")
    if lic:
        return str(lic)
    return "[À VÉRIFIER]"


def is_moe(model: dict[str, Any]) -> bool:
    blob = " ".join(_tags(model) + [str(model.get("id") or "")]).casefold()
    return any(m in blob for m in MOE_MARKERS)


def has_streaming(model: dict[str, Any]) -> bool:
    blob = " ".join(_tags(model) + [str(model.get("library_name") or "")]).casefold()
    return any(m in blob for m in STREAM_MARKERS)


def has_tool_calling(model: dict[str, Any]) -> bool:
    blob = " ".join(_tags(model) + [str(model.get("id") or "")]).casefold()
    return any(m in blob for m in TOOL_MARKERS)


def _ref_needles(category: str) -> tuple[str, ...]:
    return REFERENCE_NEEDLES.get(category, ())


_PACK_TOKENS = frozenset(
    {
        "hf",
        "gguf",
        "onnx",
        "mlx",
        "candle",
        "trfs",
        "ct2",
        "int8",
        "int4",
        "ov",
        "coreml",
        "base",
        "instruct",
        "reasoning",
        "2512",
    }
)


def _slug(model_id: str) -> str:
    return _norm(model_id.split("/")[-1])


def _slug_is_base_plus_packaging(slug: str, base: str) -> bool:
    if slug == base:
        return True
    if not slug.startswith(base + "-"):
        return False
    rest = slug[len(base) + 1 :]
    parts = [p for p in rest.split("-") if p]
    return all(p in _PACK_TOKENS or p.replace(".", "").isdigit() for p in parts)


def is_reference(model_id: str, category: str) -> bool:
    slug = _slug(model_id)
    ident = _norm(model_id)
    if category == "asr":
        for base in (
            "whisper-large-v3-turbo",
            "qwen3-asr",
            "qwen3-asr-0.6b",
            "qwen3-asr-1.7b",
            "parakeet-tdt-0.6b-v3",
            "stt-1b-en-fr",
        ):
            if _slug_is_base_plus_packaging(slug, base):
                return True
        return False
    if category == "tts":
        if _slug_is_base_plus_packaging(slug, "supertonic-3") or slug.startswith("supertonic-3-"):
            return True
        if "piper" in slug and any(tok in ident for tok in ("fr-fr", "fr_fr", "french", "-fr-", "_fr_")):
            return True
        return False
    if category == "llm":
        if slug.startswith("luciole-8b"):
            return True
        if "ministral-3-8b" in slug:
            return True
        if _slug_is_base_plus_packaging(slug, "qwen3.5-4b"):
            return True
        return False
    return False


def passes_asr_constraints(model: dict[str, Any]) -> bool:
    n = param_count(model)
    if n is not None and n > MAX_ASR_PARAMS:
        return False
    return True


def passes_tts_constraints(model: dict[str, Any]) -> bool:
    formats = set(available_formats(model))
    if formats & CPU_FORMATS:
        return True
    n = param_count(model)
    if n is None:
        return True
    if n * FP16_BYTES_PER_PARAM <= MAX_TTS_VRAM_BYTES:
        return True
    return False


def passes_llm_constraints(model: dict[str, Any]) -> bool:
    n = param_count(model)
    if n is None:
        return True
    if q4_bytes_estimate(n) > MAX_Q4_BYTES:
        return False
    if not is_moe(model) and n > MAX_DENSE_LLM_PARAMS:
        return False
    return True


CONSTRAINTS = {
    "asr": passes_asr_constraints,
    "tts": passes_tts_constraints,
    "llm": passes_llm_constraints,
}


def retain_candidate(model: dict[str, Any], category: str, now: datetime) -> bool:
    ident = str(model.get("id") or "")
    if is_reference(ident, category):
        return True
    if not in_date_window(model, now):
        return False
    return CONSTRAINTS[category](model)


def sort_candidates(models: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    def key(model: dict[str, Any]) -> tuple:
        priority = 1 if is_priority_window(model, now) else 0
        likes = int(model.get("likes") or 0)
        downloads = int(model.get("downloads") or 0)
        activity = last_activity(model) or datetime.min.replace(tzinfo=timezone.utc)
        return (priority, likes, downloads, activity)

    return sorted(models, key=key, reverse=True)


def select_top(models: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    ordered = sort_candidates(models, datetime.now(timezone.utc))
    return ordered[:n]


def format_params(n: int | None) -> str:
    if n is None:
        return "[À VÉRIFIER]"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} Md"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f} M"
    return str(n)


def format_date(model: dict[str, Any]) -> str:
    activity = last_activity(model)
    return activity.date().isoformat() if activity else "[À VÉRIFIER]"


def hf_link(model_id: str) -> str:
    return f"https://huggingface.co/{model_id}"


def _size_cell(model: dict[str, Any], category: str) -> str:
    n = param_count(model)
    base = format_params(n)
    extras: list[str] = []
    if n is None:
        return "[À VÉRIFIER]"
    if category == "llm":
        q4 = q4_bytes_estimate(n)
        extras.append(f"Q4≈{q4 / 1024**3:.1f} Go")
        if is_moe(model):
            extras.append("MoE")
    if category == "tts" and not (set(available_formats(model)) & CPU_FORMATS):
        extras.append(f"FP16≈{n * FP16_BYTES_PER_PARAM / 1024**3:.1f} Go")
    if extras:
        return f"{base} ({', '.join(extras)})"
    return base


def _lang_cell(model: dict[str, Any], category: str) -> str:
    del category
    return multilingual_declared(model)


def render_row(index: int, model: dict[str, Any], now: datetime, category: str) -> str:
    ident = str(model.get("id") or "")
    likes = model.get("likes")
    downloads = model.get("downloads")
    formats = available_formats(model)
    win = windows_native(formats, _tags(model), model.get("library_name"))
    proof = _lang_cell(model, category)
    cells = [
        str(index),
        ident,
        format_date(model),
        str(likes if likes is not None else "[À VÉRIFIER]"),
        str(downloads if downloads is not None else "[À VÉRIFIER]"),
        _size_cell(model, category),
        license_of(model),
        ", ".join(formats) if formats else "[À VÉRIFIER]",
        proof,
        win,
        hf_link(ident),
        "",
    ]
    return "| " + " | ".join(cells) + " |"


def render_table(models: list[dict[str, Any]], now: datetime, category: str = "asr") -> str:
    lang_col = "multilingue déclaré"
    header = (
        "| # | id | date | likes | téléchargements | taille | licence | "
        f"formats | {lang_col} | Windows | lien | avis |"
    )
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    rows = [render_row(i, m, now, category) for i, m in enumerate(models, start=1)]
    return "\n".join([header, sep, *rows])


def _publisher(model: dict[str, Any]) -> str:
    ident = str(model.get("id") or "")
    return ident.split("/")[0] if "/" in ident else ident


def recommend_top5(models: list[dict[str, Any]], category: str, now: datetime) -> list[tuple[dict[str, Any], str]]:
    chosen: list[dict[str, Any]] = []
    for model in models:
        if len(chosen) >= 5:
            break
        authors = {_publisher(m) for m in chosen}
        author = _publisher(model)
        slots_after = 5 - (len(chosen) + 1)
        if len(authors | {author}) + slots_after < 3:
            continue
        chosen.append(model)
    if len({_publisher(m) for m in chosen}) < 3:
        seen = {m.get("id") for m in chosen}
        for model in models:
            if model.get("id") in seen:
                continue
            chosen.append(model)
            seen.add(model.get("id"))
            if len(chosen) >= 5 and len({_publisher(m) for m in chosen}) >= 3:
                break
        chosen = chosen[:5]
    return [(m, _justification(m, category, now)) for m in chosen]


def _justification(model: dict[str, Any], category: str, now: datetime) -> str:
    bits: list[str] = []
    if is_priority_window(model, now):
        bits.append("fenêtre 30 j")
    elif in_date_window(model, now):
        bits.append("fenêtre 120 j")
    elif is_reference(str(model.get("id") or ""), category):
        bits.append("référence actuelle")
    bits.append(_lang_cell(model, category))
    bits.append(f"taille {_size_cell(model, category)}")
    formats = available_formats(model)
    bits.append("formats " + (", ".join(formats) if formats else "[À VÉRIFIER]"))
    bits.append("Windows " + windows_native(formats, _tags(model), model.get("library_name")))
    if category == "asr" and has_streaming(model):
        bits.append("streaming (tag)")
    elif category == "asr":
        bits.append("[À VÉRIFIER] streaming")
    if category == "tts":
        bits.append("[À VÉRIFIER] voix féminine grave/lente")
        if set(formats) & CPU_FORMATS:
            bits.append("CPU possible")
    if category == "llm":
        if has_tool_calling(model):
            bits.append("appel d'outils (tag)")
        else:
            bits.append("[À VÉRIFIER] appel d'outils")
    return " · ".join(bits)


def _http_get_json(url: str, timeout: int = 45) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _expand_query(grouped: bool) -> list[tuple[str, str]]:
    if grouped:
        return [("expand[]", ",".join(EXPAND_FIELDS))]
    return [("expand[]", field) for field in EXPAND_FIELDS]


def fetch_models(params: dict[str, str], *, grouped_expand: bool = True) -> list[dict[str, Any]]:
    pairs: list[tuple[str, str]] = list(params.items())
    pairs.extend(_expand_query(grouped_expand))
    url = API_MODELS + "?" + urllib.parse.urlencode(pairs)
    try:
        payload = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        if grouped_expand and exc.code in {400, 422}:
            return fetch_models(params, grouped_expand=False)
        raise
    except (TimeoutError, urllib.error.URLError):
        if grouped_expand:
            return fetch_models(params, grouped_expand=False)
        raise
    if not isinstance(payload, list):
        return []
    return [m for m in payload if isinstance(m, dict) and m.get("id")]


def fetch_model(model_id: str) -> dict[str, Any] | None:
    quoted = urllib.parse.quote(model_id, safe="")
    url = f"{API_MODELS}/{quoted}"
    try:
        payload = _http_get_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and payload.get("id"):
        return payload
    return None


def search_models(query: str, extra: dict[str, str] | None = None) -> list[dict[str, Any]]:
    params = {"search": query, "limit": "20"}
    if extra:
        params.update(extra)
    return fetch_models(params)


def _merge(dst: dict[str, dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    for model in incoming:
        ident = str(model.get("id") or "")
        if not ident:
            continue
        prev = dst.get(ident)
        if prev is None:
            dst[ident] = model
            continue
        # garder la fiche la plus riche
        if sum(1 for k in EXPAND_FIELDS if model.get(k) not in (None, [], {})) > sum(
            1 for k in EXPAND_FIELDS if prev.get(k) not in (None, [], {})
        ):
            dst[ident] = model


def sweep_category(category: str) -> list[dict[str, Any]]:
    bag: dict[str, dict[str, Any]] = {}
    if category == "asr":
        tag = "automatic-speech-recognition"
        base_queries = [
            {"pipeline_tag": tag, "sort": "trendingScore", "limit": str(LIMIT)},
            {"pipeline_tag": tag, "sort": "createdAt", "limit": str(LIMIT)},
        ]
        for author in AUDIO_AUTHORS:
            for sort in ("trendingScore", "createdAt"):
                base_queries.append(
                    {
                        "pipeline_tag": tag,
                        "author": author,
                        "sort": sort,
                        "limit": str(LIMIT),
                    }
                )
    elif category == "tts":
        tag = "text-to-speech"
        base_queries = [
            {"pipeline_tag": tag, "sort": "trendingScore", "limit": str(LIMIT)},
            {"pipeline_tag": tag, "sort": "createdAt", "limit": str(LIMIT)},
        ]
        for author in AUDIO_AUTHORS:
            for sort in ("trendingScore", "createdAt"):
                base_queries.append(
                    {
                        "pipeline_tag": tag,
                        "author": author,
                        "sort": sort,
                        "limit": str(LIMIT),
                    }
                )
    else:
        base_queries = [
            {
                "pipeline_tag": "text-generation",
                "library": "gguf",
                "sort": "trendingScore",
                "limit": str(LIMIT),
            },
            {
                "pipeline_tag": "text-generation",
                "library": "gguf",
                "sort": "createdAt",
                "limit": str(LIMIT),
            },
        ]
        for author in LLM_AUTHORS:
            for sort in ("trendingScore", "createdAt"):
                base_queries.append(
                    {
                        "pipeline_tag": "text-generation",
                        "library": "gguf",
                        "author": author,
                        "sort": sort,
                        "limit": str(LIMIT),
                    }
                )
                base_queries.append(
                    {
                        "pipeline_tag": "text-generation",
                        "author": author,
                        "sort": sort,
                        "limit": str(LIMIT),
                    }
                )

    for params in base_queries:
        try:
            _merge(bag, fetch_models(params))
        except Exception as exc:  # noqa: BLE001 — une requête ne doit pas tuer la nuit
            print(f"WARN fetch {params}: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(SLEEP_S)

    extra = {}
    if category == "asr":
        extra = {"pipeline_tag": "automatic-speech-recognition"}
    elif category == "tts":
        extra = {"pipeline_tag": "text-to-speech"}
    elif category == "llm":
        extra = {"pipeline_tag": "text-generation"}

    for query in REFERENCE_SEARCHES[category]:
        try:
            hits = search_models(query, extra)
            _merge(bag, hits)
            for hit in hits[:8]:
                ident = str(hit.get("id") or "")
                if ident and (
                    is_reference(ident, category)
                    or _norm(query).replace(" ", "-") in _norm(ident)
                ):
                    full = fetch_model(ident)
                    if full:
                        _merge(bag, [full])
                    time.sleep(SLEEP_S)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN search {query}: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(SLEEP_S)

    return list(bag.values())


def filter_category(models: list[dict[str, Any]], category: str, now: datetime) -> list[dict[str, Any]]:
    kept = [m for m in models if retain_candidate(m, category, now)]
    return sort_candidates(kept, now)


def collect_references(models: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
    refs = [m for m in models if is_reference(str(m.get("id") or ""), category)]
    return sorted(refs, key=lambda m: str(m.get("id") or ""))


def render_report(
    *,
    now: datetime,
    asr: list[dict[str, Any]],
    tts: list[dict[str, Any]],
    llm: list[dict[str, Any]],
    asr_all: list[dict[str, Any]],
    tts_all: list[dict[str, Any]],
    llm_all: list[dict[str, Any]],
) -> str:
    del asr_all, tts_all
    lines = [
        f"# Veille Hugging Face — {now.date().isoformat()}",
        "",
        "Généré par `dev/scripts/veille_hf.py` via l'API publique `https://huggingface.co/api/models` (sans jeton).",
        f"Fenêtre : créés ou modifiés depuis **{WINDOW_DAYS} jours** (priorité aux **{PRIORITY_DAYS}** derniers jours).",
        "Balayage : `sort=trendingScore` et `sort=createdAt`, `limit=100`, plus `author=` des éditeurs.",
        "Aucun poids téléchargé. Les champs non prouvés par l'API sont marqués `[À VÉRIFIER]`.",
        "Colonne **avis** : à compléter à la main (vide à la génération).",
        "",
    ]
    lines.extend(render_asr_section(now, asr).splitlines())
    lines.append("")
    lines.extend(render_tts_section(now, tts).splitlines())
    lines.append("")
    lines.extend(render_llm_section(now, llm, llm_all).splitlines())
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_asr_section(now: datetime, asr: list[dict[str, Any]]) -> str:
    asr15 = asr[:15]
    asr5 = recommend_top5(asr15, "asr", now)
    lines = [
        "## ASR (oreille)",
        "",
        "Contraintes : ≤ 2 Md param. · streaming = bonus · **pas de filtre tag `fr`**.",
        "Balayage : `pipeline_tag=automatic-speech-recognition`, `sort=trendingScore` et `sort=createdAt`, `limit=100`, fenêtre 120 jours ; plus les dépôts `author=` des éditeurs généralistes.",
        "Colonne **multilingue déclaré** : tag `fr`, ou liste de langues dans `cardData`, ou mention `multilingual` — sinon `[À VÉRIFIER]`.",
        "",
        "### Top 15 candidats",
        "",
        render_table(asr15, now, "asr"),
        "",
        "### Top 5 recommandé",
        "",
    ]
    lines.extend(_render_reco(asr5))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_tts_section(now: datetime, tts: list[dict[str, Any]]) -> str:
    tts15 = tts[:15]
    tts5 = recommend_top5(tts15, "tts", now)
    lines = [
        "## TTS (voix)",
        "",
        "Contraintes : voix féminine grave/lente possible · CPU ou ≤ 2 Go VRAM · **pas de filtre tag `fr`**.",
        "Balayage : `pipeline_tag=text-to-speech`, `sort=trendingScore` et `sort=createdAt`, `limit=100`, fenêtre 120 jours ; plus les dépôts `author=` des éditeurs généralistes.",
        "Colonne **multilingue déclaré** : tag `fr`, ou liste de langues dans `cardData`, ou mention `multilingual` — sinon `[À VÉRIFIER]`.",
        "",
        "### Top 15 candidats",
        "",
        render_table(tts15, now, "tts"),
        "",
        "### Top 5 recommandé",
        "",
    ]
    lines.extend(_render_reco(tts5))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_llm_section(
    now: datetime,
    llm: list[dict[str, Any]],
    llm_all: list[dict[str, Any]] | None = None,
) -> str:
    del llm_all  # plus de dump références : le tag fr n'est plus un filtre
    llm15 = llm[:15]
    llm5 = recommend_top5(llm15, "llm", now)
    lines = [
        "## LLM (cerveau)",
        "",
        "Contraintes : Q4 ≲ 6 Go (dense ≲ 9 Md, ou MoE dont le Q4 ≲ 6 Go) · **pas de filtre tag `fr`** (biais : les grands LLM multilingues ne taguent souvent pas `fr`) · appel d'outils = bonus.",
        "Balayage : `pipeline_tag=text-generation` + `library=gguf`, `sort=trendingScore` et `sort=createdAt`, `limit=100`, fenêtre 120 jours ; plus les dépôts `author=` des éditeurs principaux.",
        "Colonne **multilingue déclaré** : tag `fr`, ou liste de langues dans `cardData`, ou mention `multilingual` — sinon `[À VÉRIFIER]`.",
        "",
        "### Top 15 candidats",
        "",
        render_table(llm15, now, "llm"),
        "",
        "### Top 5 recommandé",
        "",
    ]
    lines.extend(_render_reco(llm5))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def splice_llm_section(old: str, section: str) -> str:
    marker = "## LLM (cerveau)"
    idx = old.find(marker)
    if idx == -1:
        return old.rstrip() + "\n\n" + section.lstrip()
    return old[:idx] + section.lstrip()


def splice_asr_tts_sections(old: str, asr_section: str, tts_section: str) -> str:
    asr_mark = "## ASR (oreille)"
    llm_mark = "## LLM (cerveau)"
    start = old.find(asr_mark)
    llm = old.find(llm_mark)
    prefix = old[:start] if start != -1 else old.rstrip() + "\n\n"
    suffix = old[llm:] if llm != -1 else ""
    mid = asr_section.rstrip() + "\n\n" + tts_section.lstrip()
    if suffix:
        return prefix + mid.rstrip() + "\n\n" + suffix.lstrip()
    return prefix + mid.rstrip() + "\n"


def _render_reco(items: list[tuple[dict[str, Any], str]]) -> list[str]:
    if not items:
        return ["_Aucun candidat retenu._"]
    out: list[str] = []
    for i, (model, why) in enumerate(items, start=1):
        ident = model.get("id")
        out.append(f"{i}. **{ident}** — {why}")
    return out


def default_output_path(now: datetime) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "nights" / f"{now.date().isoformat()}-VEILLE-HF.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Veille HF par API publique (stdlib).")
    parser.add_argument("--out", type=Path, default=None, help="Chemin du markdown de sortie.")
    parser.add_argument(
        "--section",
        choices=("all", "llm", "asr-tts"),
        default="all",
        help="all = rapport complet ; llm/asr-tts = remplace uniquement ces sections.",
    )
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    dest = args.out or default_output_path(now)

    if args.section == "asr-tts":
        print("Balayage ASR…", flush=True)
        asr_all = sweep_category("asr")
        print(f"  {len(asr_all)} fiches", flush=True)
        print("Balayage TTS…", flush=True)
        tts_all = sweep_category("tts")
        print(f"  {len(tts_all)} fiches", flush=True)
        asr = filter_category(asr_all, "asr", now)
        tts = filter_category(tts_all, "tts", now)
        print(f"Retenus ASR={len(asr)} TTS={len(tts)}", flush=True)
        asr_sec = render_asr_section(now, asr)
        tts_sec = render_tts_section(now, tts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.write_text(
                splice_asr_tts_sections(dest.read_text(encoding="utf-8"), asr_sec, tts_sec),
                encoding="utf-8",
            )
        else:
            dest.write_text(asr_sec.rstrip() + "\n\n" + tts_sec, encoding="utf-8")
        print(f"Écrit sections ASR+TTS dans {dest}", flush=True)
        return 0

    if args.section == "llm":
        print("Balayage LLM…", flush=True)
        llm_all = sweep_category("llm")
        print(f"  {len(llm_all)} fiches", flush=True)
        llm = filter_category(llm_all, "llm", now)
        print(f"Retenus LLM={len(llm)}", flush=True)
        section = render_llm_section(now, llm, llm_all)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.write_text(splice_llm_section(dest.read_text(encoding="utf-8"), section), encoding="utf-8")
        else:
            dest.write_text(section, encoding="utf-8")
        print(f"Écrit section LLM dans {dest}", flush=True)
        return 0

    print("Balayage ASR…", flush=True)
    asr_all = sweep_category("asr")
    print(f"  {len(asr_all)} fiches", flush=True)
    print("Balayage TTS…", flush=True)
    tts_all = sweep_category("tts")
    print(f"  {len(tts_all)} fiches", flush=True)
    print("Balayage LLM…", flush=True)
    llm_all = sweep_category("llm")
    print(f"  {len(llm_all)} fiches", flush=True)

    asr = filter_category(asr_all, "asr", now)
    tts = filter_category(tts_all, "tts", now)
    llm = filter_category(llm_all, "llm", now)
    print(f"Retenus ASR={len(asr)} TTS={len(tts)} LLM={len(llm)}", flush=True)

    report = render_report(
        now=now,
        asr=asr,
        tts=tts,
        llm=llm,
        asr_all=asr_all,
        tts_all=tts_all,
        llm_all=llm_all,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(report, encoding="utf-8")
    print(f"Écrit {dest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
