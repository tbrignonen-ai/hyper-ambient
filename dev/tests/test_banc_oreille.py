"""Banc oreille : format, anonymisation, dotenv — sans GPU ni réseau."""
from __future__ import annotations

import json
import wave
from pathlib import Path

from dev.scripts.banc_oreille import (
    CANDIDATS,
    anonymiser,
    choisir_device_whisper,
    duree_wav_s,
    extraire_texte_sse,
    filtrer_candidats,
    fusionner_bruts,
    kwargs_transcribe_whisper,
    lister_wav,
    parser_env_local,
    rendre_resultats_md,
    rtf,
    vram_propre_mib,
    windows_natif,
)


def _fichier_env(tmp_path: Path, lignes: list[bytes]) -> Path:
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(b"".join(lignes))
    return chemin


def _wav_silence(tmp_path: Path, nom: str = "a.wav", nframes: int = 16000) -> Path:
    chemin = tmp_path / nom
    with wave.open(str(chemin), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * nframes)
    return chemin


def test_six_candidats_dans_l_ordre_du_brief():
    assert [c["id"] for c in CANDIDATS[:6]] == [
        "whisper-turbo",
        "qwen3-asr",
        "parakeet",
        "nemotron",
        "kyutai",
        "stepaudio",
    ]
    assert CANDIDATS[0]["modele"] == "openai/whisper-large-v3-turbo"
    assert CANDIDATS[1]["modele"] == "Qwen/Qwen3-ASR-0.6B"
    assert CANDIDATS[2]["modele"] == "nvidia/parakeet-tdt-0.6b-v3"
    assert CANDIDATS[3]["modele"] == "nvidia/nemotron-3.5-asr-streaming-0.6b"
    assert CANDIDATS[4]["modele"] == "kyutai/stt-1b-en_fr"
    assert CANDIDATS[5]["modele"] == "stepaudio-2.5-asr"


def test_env_local_crlf_ne_colle_pas_de_retour_chariot(tmp_path):
    chemin = _fichier_env(
        tmp_path,
        [b"STEPFUN_API_KEY=jeton-step-32\r\n", b"AUTRE=ignoree\n"],
    )
    paires = parser_env_local(chemin)
    assert paires["STEPFUN_API_KEY"] == "jeton-step-32"
    assert "\r" not in paires["STEPFUN_API_KEY"]


def test_lister_wav_trie_et_ignore_le_reste(tmp_path):
    _wav_silence(tmp_path, "b.wav")
    _wav_silence(tmp_path, "a.wav")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    noms = [p.name for p in lister_wav(tmp_path)]
    assert noms == ["a.wav", "b.wav"]


def test_duree_et_rtf(tmp_path):
    wav = _wav_silence(tmp_path, nframes=32000)
    assert duree_wav_s(wav) == 2.0
    assert rtf(0.5, 2.0) == 0.25
    assert rtf(1.0, 0.0) is None


def test_windows_natif_selon_la_voie():
    assert windows_natif("faster-whisper") == "oui"
    assert windows_natif("qwen3") == "à vérifier"
    assert windows_natif("sherpa-onnx") == "oui"
    assert windows_natif("nemo-speech-gguf") == "oui"
    assert windows_natif("nemo") == "à vérifier"
    assert windows_natif("moshi") == "à vérifier"
    assert windows_natif("http-distant") == "oui"


def test_anonymiser_o1_o6_et_carte_secrete():
    bruts = [
        {
            "id": c["id"],
            "modele": c["modele"],
            "texte": f"phrase {i}",
            "temps_s": 1.0,
            "rtf": 0.1,
            "vram_max_mib": 100,
            "windows_natif": "oui",
            "erreur": None,
            "voie": c["voie"],
        }
            for i, c in enumerate(CANDIDATS[:6], start=1)
    ]
    anonymes, carte = anonymiser(bruts)
    assert [a["code"] for a in anonymes] == ["O1", "O2", "O3", "O4", "O5", "O6"]
    assert carte["O1"]["id"] == "whisper-turbo"
    assert carte["O6"]["modele"] == "stepaudio-2.5-asr"
    assert "whisper" not in anonymes[0]["texte"]


def test_resultats_md_anonyme_sans_noms_de_modeles():
    anonymes = [
        {
            "code": "O1",
            "fichier": "voix-F5.wav",
            "texte": "Bonjour.",
            "temps_s": 0.42,
            "rtf": 0.05,
            "vram_max_mib": 512,
            "windows_natif": "oui",
            "erreur": None,
        }
    ]
    md = rendre_resultats_md(anonymes)
    assert "| O1 |" in md
    assert "whisper" not in md.lower()
    assert "qwen" not in md.lower()
    assert "stepfun" not in md.lower()
    assert "Bonjour." in md


def test_extraire_texte_sse_prend_le_done():
    flux = (
        'data: {"type":"transcript.text.delta","text":"Bon"}\n\n'
        'data: {"type":"transcript.text.done","text":"Bonjour Thomas."}\n\n'
    )
    assert extraire_texte_sse(flux) == "Bonjour Thomas."


def test_whisper_large_v3_candidat_faster_whisper():
    cand = next(c for c in CANDIDATS if c["id"] == "whisper-large-v3")
    assert cand["modele"] == "openai/whisper-large-v3"
    assert cand["voie"] == "faster-whisper"
    assert cand["venv"] == "whisper-large-v3"
    assert cand.get("fw") == "large-v3"


def test_choisir_device_whisper_gpu_si_4go_libres():
    assert choisir_device_whisper(4096) == ("cuda", "int8_float16")
    assert choisir_device_whisper(4095) == ("cpu", "int8")
    assert choisir_device_whisper(None) == ("cpu", "int8")


def test_filtrer_candidats_par_id_ne_prend_que_whisper_large_v3():
    seuls = filtrer_candidats(CANDIDATS, ["whisper-large-v3"])
    assert [c["id"] for c in seuls] == ["whisper-large-v3"]


def test_fusionner_bruts_ajoute_sans_effacer_les_autres():
    existants = [
        {"id": "whisper-turbo", "fichier": "a.wav", "texte": "ancien"},
        {"id": "qwen3-asr", "fichier": "a.wav", "texte": "reste"},
    ]
    nouveaux = [
        {"id": "whisper-large-v3", "fichier": "a.wav", "texte": "neuf"},
    ]
    fusion = fusionner_bruts(existants, nouveaux)
    assert [b["id"] for b in fusion] == ["whisper-turbo", "qwen3-asr", "whisper-large-v3"]
    assert fusion[1]["texte"] == "reste"
    assert fusion[2]["texte"] == "neuf"


def test_fusionner_bruts_remplace_meme_id_et_fichier():
    existants = [
        {"id": "whisper-turbo", "fichier": "a.wav", "texte": "reste"},
        {"id": "canary", "fichier": "a.wav", "texte": "", "erreur": "fail"},
        {"id": "canary", "fichier": "b.wav", "texte": "garde"},
    ]
    nouveaux = [
        {"id": "canary", "fichier": "a.wav", "texte": "ok", "erreur": None},
    ]
    fusion = fusionner_bruts(existants, nouveaux)
    assert [b["id"] for b in fusion] == ["whisper-turbo", "canary", "canary"]
    assert fusion[1]["fichier"] == "a.wav" and fusion[1]["texte"] == "ok"
    assert fusion[2]["fichier"] == "b.wav" and fusion[2]["texte"] == "garde"


def test_canary_candidat_onnx_asr():
    cand = next(c for c in CANDIDATS if c["id"] == "canary")
    assert cand["modele"] == "nvidia/canary-1b-v2"
    assert cand["voie"] == "onnx-asr"
    assert cand["venv"] == "canary"
    assert windows_natif(cand["voie"]) == "oui"


def test_filtrer_candidats_par_id_ne_prend_que_canary():
    seuls = filtrer_candidats(CANDIDATS, ["canary"])
    assert [c["id"] for c in seuls] == ["canary"]


def test_vram_propre_mib_delta_avant_apres_chargement():
    assert vram_propre_mib(6000, 8500) == 2500
    assert vram_propre_mib(None, 100) is None
    assert vram_propre_mib(100, None) is None
    assert vram_propre_mib(8000, 7900) == 0


def test_kwargs_transcribe_whisper_hotwords():
    base = kwargs_transcribe_whisper("")
    assert "hotwords" not in base
    assert base["language"] == "fr"
    hw = kwargs_transcribe_whisper("Hyper Ambient")
    assert hw["hotwords"] == "Hyper Ambient"
