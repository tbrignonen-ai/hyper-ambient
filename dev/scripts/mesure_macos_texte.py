"""Mesure manuelle sur Mac 16 Go du tri MLX et de la réponse réflexe.

Usage : python -m dev.scripts.mesure_macos_texte --pid <PID text_server>
Le serveur texte du profil doit déjà tourner. Aucun modèle n'est chargé ici.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request

from src.brain.factory import MODELE_MLX_CHARGE, SORTIE_REFLEXE_MLX
from src.brain.router import CLASSIFY_PREFIX, CLASSIFY_SUFFIX, normaliser_verdict

PHRASES = [
    ("Bonjour hyper-ambient.", "REFLEXE"),
    ("Merci, c'est noté.", "REFLEXE"),
    ("Je suis un peu stressé pour ma soutenance cet après-midi.", "REFLEXE"),
    ("Tu peux me raconter comment tu fonctionnes ?", "REFLEXE"),
    ("Répète plus fort.", "REFLEXE"),
    ("Explique-moi la différence entre TCP et UDP.", "ESCALADE"),
    ("Quelle est la capitale de la Norvège ?", "ESCALADE"),
    ("Il est 14 h 40, ma réunion dure quarante minutes et commence dans vingt minutes, à quelle heure je finis ?", "ESCALADE"),
    ("Quel temps fait-il à Paris demain ?", "ESCALADE"),
]


def rss_mib(pid):
    if pid is None:
        return None
    try:
        return round(int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)],
                                                 text=True, timeout=3).strip()) / 1024, 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def appel(endpoint, messages, max_tokens):
    body = json.dumps({"model": MODELE_MLX_CHARGE, "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0,
                       "stream": False}, ensure_ascii=False).encode("utf-8")
    debut = time.perf_counter()
    requete = urllib.request.Request(endpoint, data=body,
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=120) as reponse:
        result = json.load(reponse)
    return result, round((time.perf_counter() - debut) * 1000)


def mesurer(endpoint, pid=None):
    resultats = []
    for phrase, attendu in PHRASES:
        result, ms = appel(endpoint, [
            {"role": "system", "content": "Réponds exclusivement REFLEXE ou ESCALADE."},
            {"role": "user", "content": CLASSIFY_PREFIX + phrase + CLASSIFY_SUFFIX},
        ], 8)
        choix = result["choices"][0]
        verdict = normaliser_verdict(choix["message"]["content"])
        resultats.append({"phrase": phrase, "attendu": attendu, "verdict": verdict,
                          "correct": verdict == attendu, "latence_ms": ms,
                          "rss_mib": rss_mib(pid)})
    conversation, ms = appel(endpoint, [
        {"role": "system", "content": "Réponds naturellement en français, en phrases complètes."},
        {"role": "user", "content": "Je suis stressé pour ma soutenance. Tu peux rester avec moi un instant ?"},
    ], SORTIE_REFLEXE_MLX)
    choix = conversation["choices"][0]
    return {"classification": resultats,
            "reflexe": {"latence_ms": ms, "finish_reason": choix.get("finish_reason"),
                        "caracteres": len(choix["message"].get("content") or ""),
                        "usage": conversation.get("usage"), "rss_mib": rss_mib(pid)},
            "max_tokens_reflexe": SORTIE_REFLEXE_MLX}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    rapport = mesurer(args.endpoint, args.pid)
    texte = json.dumps(rapport, ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0 if all(x["correct"] for x in rapport["classification"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
