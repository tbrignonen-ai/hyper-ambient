"""Filtres et tris de veille_hf — JSON fictif, sans réseau."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dev.scripts.veille_hf import (
    available_formats,
    french_proof,
    in_date_window,
    is_priority_window,
    is_reference,
    license_of,
    multilingual_declared,
    param_count,
    passes_asr_constraints,
    passes_llm_constraints,
    passes_tts_constraints,
    q4_bytes_estimate,
    recommend_top5,
    render_table,
    retain_candidate,
    select_top,
    sort_candidates,
    windows_native,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _model(**overrides):
    raw = {
        "id": "org/modele-fr",
        "pipeline_tag": "automatic-speech-recognition",
        "library_name": "transformers",
        "tags": ["automatic-speech-recognition", "fr"],
        "likes": 100,
        "downloads": 10_000,
        "createdAt": "2026-09-01T00:00:00.000Z",
        "lastModified": "2026-09-10T00:00:00.000Z",
        "safetensors": {"total": 600_000_000},
        "cardData": {"license": "apache-2.0", "language": ["fr"]},
    }
    raw.update(overrides)
    return raw


def test_in_date_window_accepte_modifie_dans_120j():
    recent = _model(lastModified=(NOW - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    assert in_date_window(recent, NOW, days=120) is True


def test_in_date_window_accepte_cree_dans_120j_meme_si_mod_ancienne():
    created = (NOW - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    old_mod = (NOW - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    raw = _model(createdAt=created, lastModified=old_mod)
    assert in_date_window(raw, NOW, days=120) is True


def test_in_date_window_refuse_hors_120j():
    old = (NOW - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    raw = _model(createdAt=old, lastModified=old)
    assert in_date_window(raw, NOW, days=120) is False


def test_is_priority_window_30j():
    young_d = (NOW - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    older_d = (NOW - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    young = _model(createdAt=young_d, lastModified=young_d)
    older = _model(createdAt=older_d, lastModified=older_d)
    assert is_priority_window(young, NOW, days=30) is True
    assert is_priority_window(older, NOW, days=30) is False


def test_param_count_prefers_safetensors_total():
    assert param_count(_model(safetensors={"total": 600_000_000})) == 600_000_000


def test_param_count_gguf_si_pas_safetensors():
    raw = _model()
    del raw["safetensors"]
    raw["gguf"] = {"total": 8_000_000_000}
    assert param_count(raw) == 8_000_000_000


def test_param_count_absent():
    raw = _model()
    del raw["safetensors"]
    assert param_count(raw) is None


def test_q4_bytes_estimate_8b_sous_6go():
    assert q4_bytes_estimate(8_000_000_000) < 6 * 1024**3


def test_q4_bytes_estimate_14b_au_dessus_6go():
    assert q4_bytes_estimate(14_000_000_000) > 6 * 1024**3


def test_french_proof_tag_fr():
    proof = french_proof(_model(tags=["asr", "fr"], cardData={"license": "mit"}))
    assert "tag `fr`" in proof
    assert not proof.startswith("[À VÉRIFIER]")


def test_french_proof_carddata_language():
    proof = french_proof(
        _model(tags=["asr"], cardData={"license": "mit", "language": ["fra"]})
    )
    assert "cardData.language" in proof
    assert "fra" in proof


def test_french_proof_absent_est_a_verifier():
    proof = french_proof(
        _model(id="org/modele-en", tags=["en"], cardData={"license": "mit", "language": ["en"]})
    )
    assert proof.startswith("[À VÉRIFIER]")


def test_available_formats_depuis_objets_et_tags():
    raw = _model(
        tags=["onnx", "gguf"],
        safetensors={"total": 1},
        gguf={"total": 1},
    )
    formats = available_formats(raw)
    assert "gguf" in formats
    assert "onnx" in formats
    assert "safetensors" in formats


def test_available_formats_ctranslate2():
    formats = available_formats(_model(tags=["ctranslate2"], library_name="ctranslate2"))
    assert "ctranslate2" in formats


def test_windows_native_gguf_oui_probable():
    assert windows_native(["gguf"], [], "llama.cpp") == "oui probable"


def test_windows_native_nemo_a_verifier():
    assert windows_native([], ["nemo"], "nemo") == "à vérifier"


def test_license_of_carddata():
    assert license_of(_model(cardData={"license": "mit"})) == "mit"


def test_license_of_absente():
    assert license_of(_model(cardData={})) == "[À VÉRIFIER]"


def test_passes_asr_taille_sans_exiger_fr():
    assert passes_asr_constraints(_model(safetensors={"total": 600_000_000})) is True
    gros = _model(safetensors={"total": 3_000_000_000})
    assert passes_asr_constraints(gros) is False
    sans_fr = _model(
        id="openai/whisper-tiny",
        tags=["en"],
        cardData={"license": "mit", "language": ["en"]},
        safetensors={"total": 39_000_000},
    )
    assert passes_asr_constraints(sans_fr) is True


def test_passes_asr_taille_inconnue_ok_si_fr():
    raw = _model()
    del raw["safetensors"]
    assert passes_asr_constraints(raw) is True


def test_passes_tts_sans_tag_fr_si_cpu():
    raw = _model(
        id="microsoft/speecht5_tts",
        pipeline_tag="text-to-speech",
        tags=["text-to-speech", "onnx"],
        library_name="onnx",
        cardData={"license": "openrail"},
        safetensors={"total": 80_000_000},
    )
    assert passes_tts_constraints(raw) is True


def test_passes_tts_cpu_format_passe():
    raw = _model(
        pipeline_tag="text-to-speech",
        tags=["text-to-speech", "fr", "onnx"],
        library_name="onnx",
        safetensors={"total": 80_000_000},
    )
    assert passes_tts_constraints(raw) is True


def test_passes_tts_gros_sans_format_cpu_refuse():
    raw = _model(
        pipeline_tag="text-to-speech",
        tags=["text-to-speech", "fr"],
        library_name="transformers",
        safetensors={"total": 3_000_000_000},
    )
    raw.pop("gguf", None)
    assert passes_tts_constraints(raw) is False


def test_passes_llm_sans_tag_fr_si_taille_ok():
    raw = _model(
        id="Qwen/Qwen3.5-4B-GGUF",
        pipeline_tag="text-generation",
        tags=["text-generation", "gguf"],
        library_name="gguf",
        cardData={"license": "apache-2.0", "language": ["en"]},
        safetensors=None,
        gguf={"total": 4_000_000_000},
    )
    raw.pop("safetensors", None)
    assert passes_llm_constraints(raw) is True


def test_multilingual_declared_tag_fr():
    proof = multilingual_declared(_model(tags=["text-generation", "fr"], cardData={}))
    assert "tag `fr`" in proof
    assert not proof.startswith("[À VÉRIFIER]")


def test_multilingual_declared_liste_langues_carddata():
    proof = multilingual_declared(
        _model(id="Qwen/Qwen3.5-4B", tags=["text-generation"], cardData={"language": ["en", "zh"]})
    )
    assert "cardData.language" in proof
    assert "en" in proof


def test_multilingual_declared_mention_multilingual():
    proof = multilingual_declared(
        _model(id="org/modele-en", tags=["text-generation", "multilingual"], cardData={})
    )
    assert "multilingual" in proof.casefold()
    assert not proof.startswith("[À VÉRIFIER]")


def test_multilingual_declared_absent():
    proof = multilingual_declared(
        _model(id="org/modele-en", tags=["text-generation"], cardData={"license": "mit"})
    )
    assert proof.startswith("[À VÉRIFIER]")


def test_recommend_top5_asr_au_moins_3_editeurs():
    def asr(ident: str, likes: int) -> dict:
        return _model(id=ident, likes=likes, safetensors={"total": 600_000_000})

    models = [
        asr("openai/a", 500),
        asr("openai/b", 400),
        asr("openai/c", 300),
        asr("openai/d", 200),
        asr("openai/e", 100),
        asr("Qwen/f", 50),
        asr("nvidia/g", 40),
    ]
    picked = recommend_top5(models, "asr", NOW)
    authors = {m["id"].split("/")[0] for m, _ in picked}
    assert len(picked) == 5
    assert len(authors) >= 3


def test_recommend_top5_tts_au_moins_3_editeurs():
    def tts(ident: str, likes: int) -> dict:
        return _model(
            id=ident,
            likes=likes,
            pipeline_tag="text-to-speech",
            tags=["text-to-speech", "onnx"],
            library_name="onnx",
            safetensors={"total": 80_000_000},
        )

    models = [
        tts("Supertone/a", 500),
        tts("Supertone/b", 400),
        tts("Supertone/c", 300),
        tts("Supertone/d", 200),
        tts("Supertone/e", 100),
        tts("neuphonic/f", 50),
        tts("Edge0/g", 40),
    ]
    picked = recommend_top5(models, "tts", NOW)
    authors = {m["id"].split("/")[0] for m, _ in picked}
    assert len(picked) == 5
    assert len(authors) >= 3


def test_recommend_top5_llm_au_moins_3_editeurs():
    def llm(ident: str, likes: int) -> dict:
        return _model(
            id=ident,
            likes=likes,
            pipeline_tag="text-generation",
            tags=["text-generation", "gguf"],
            library_name="gguf",
            cardData={"license": "apache-2.0"},
            safetensors=None,
            gguf={"total": 4_000_000_000},
        )

    models = [
        llm("Qwen/a", 500),
        llm("Qwen/b", 400),
        llm("Qwen/c", 300),
        llm("Qwen/d", 200),
        llm("Qwen/e", 100),
        llm("google/f", 50),
        llm("mistralai/g", 40),
    ]
    picked = recommend_top5(models, "llm", NOW)
    authors = {m["id"].split("/")[0] for m, _ in picked}
    assert len(picked) == 5
    assert len(authors) >= 3


def test_render_table_asr_et_tts_colonne_multilingue():
    for cat in ("asr", "tts"):
        md = render_table([_model(id="org/modele")], NOW, category=cat)
        assert "multilingue déclaré" in md
        assert "preuve FR" not in md


def test_render_table_llm_colonne_multilingue():
    md = render_table([_model(id="Qwen/Qwen3.5-4B")], NOW, category="llm")
    assert "multilingue déclaré" in md
    assert "preuve FR" not in md


def test_passes_llm_8b_gguf_ok():
    raw = _model(
        pipeline_tag="text-generation",
        tags=["text-generation", "fr", "gguf"],
        library_name="gguf",
        safetensors=None,
        gguf={"total": 8_000_000_000},
    )
    raw.pop("safetensors", None)
    assert passes_llm_constraints(raw) is True


def test_passes_llm_14b_dense_refuse():
    raw = _model(
        pipeline_tag="text-generation",
        tags=["text-generation", "fr", "gguf"],
        library_name="gguf",
        safetensors=None,
        gguf={"total": 14_000_000_000},
    )
    raw.pop("safetensors", None)
    assert passes_llm_constraints(raw) is False


def test_passes_llm_moe_q4_trop_gros_refuse():
    raw = _model(
        pipeline_tag="text-generation",
        tags=["text-generation", "fr", "gguf", "moe"],
        library_name="gguf",
        safetensors=None,
        gguf={"total": 30_000_000_000},
    )
    raw.pop("safetensors", None)
    assert passes_llm_constraints(raw) is False


def test_sort_priority_30j_avant_plus_vieux_meme_si_moins_de_likes():
    jeune = _model(
        id="org/jeune",
        likes=10,
        downloads=10,
        lastModified=(NOW - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        createdAt=(NOW - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    )
    vieux = _model(
        id="org/vieux",
        likes=10_000,
        downloads=1_000_000,
        lastModified=(NOW - timedelta(days=80)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        createdAt=(NOW - timedelta(days=80)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    )
    ordered = sort_candidates([vieux, jeune], NOW)
    assert [m["id"] for m in ordered] == ["org/jeune", "org/vieux"]


def test_select_top_15():
    models = [_model(id=f"org/m{i}", likes=i) for i in range(20)]
    assert len(select_top(models, n=15)) == 15
    assert select_top(models, n=15)[0]["id"] == "org/m19"


def test_is_reference_asr():
    assert is_reference("openai/whisper-large-v3-turbo", "asr") is True
    assert is_reference("Qwen/Qwen3-ASR-0.6B", "asr") is True
    assert is_reference("org/inconnu", "asr") is False
    assert is_reference("thorhojhus/whisper-large-v3-turbo-danish", "asr") is False


def test_retain_reference_hors_fenetre():
    old = (NOW - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    raw = _model(
        id="openai/whisper-large-v3-turbo",
        createdAt=old,
        lastModified=old,
        safetensors={"total": 809_000_000},
    )
    assert retain_candidate(raw, "asr", NOW) is True


def test_retain_refuse_hors_fenetre_non_ref():
    old = (NOW - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    raw = _model(id="org/vieux-asr", createdAt=old, lastModified=old)
    assert retain_candidate(raw, "asr", NOW) is False


def test_render_table_colonnes_et_avis_vide():
    md = render_table([_model()], NOW)
    for col in (
        "id",
        "date",
        "likes",
        "téléchargements",
        "taille",
        "licence",
        "formats",
        "multilingue déclaré",
        "Windows",
        "lien",
        "avis",
    ):
        assert col in md
    rows = [line for line in md.splitlines() if line.startswith("| 1 |")]
    assert rows, md
    avis = rows[0].rstrip("|").split("|")[-1].strip()
    assert avis == ""
