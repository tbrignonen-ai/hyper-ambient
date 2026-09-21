#!/usr/bin/env python3
"""Chemin écrit : même pipeline cerveau que le tour vocal, sans EARS ni MOUTH.

    python3 dev/scripts/parler_ecrit.py
    python3 dev/scripts/parler_ecrit.py "Bonjour, comment vas-tu ?"
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CHEMIN_SERVEUR = Path(__file__).resolve().parent / "serve_hostagent.py"
_spec = importlib.util.spec_from_file_location("serve_hostagent", _CHEMIN_SERVEUR)
_serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_serve)

from src.brain.contexte import (
    MemoireConversation,
    canal_porteur,
    phrase_garde,
    question_d_outil,
)

monter_cerveau = _serve.monter_cerveau
flux_cerveau = _serve.flux_cerveau
recoller_prononce = _serve.recoller_prononce
nouveau_fichier_conversation = _serve.nouveau_fichier_conversation
ecrire_ligne_conversation = _serve.ecrire_ligne_conversation
NOM_HARNAIS_PAR_OUTIL = _serve.NOM_HARNAIS_PAR_OUTIL
MEMOIRE_MESSAGES = _serve.MEMOIRE_MESSAGES
_appliquer_env_boot = _serve._appliquer_env_boot


def _harnais(nom_outil: str) -> str:
    return NOM_HARNAIS_PAR_OUTIL.get(nom_outil, nom_outil)


async def jouer_tour_ecrit(prompt: str, pieces: dict) -> dict:
    """Un tour texte : même flux cerveau, stdout au lieu de MOUTH."""
    t0 = time.monotonic()
    journal = pieces.get("journal")
    memoire = pieces.get("memoire")
    if memoire is None:
        memoire = MemoireConversation()
        pieces["memoire"] = memoire
    if memoire.doit_fermer(mains_libres=False, maintenant=time.monotonic()):
        garde = phrase_garde(
            [m.harnais for m in (pieces.get("mandats").en_cours() if pieces.get("mandats") else [])]
        )
        memoire.purger()
        pieces["historique"] = []
        if garde:
            print(garde, flush=True)
            ecrire_ligne_conversation(journal, "hyper-ambient", garde)
    ecrire_ligne_conversation(journal, "Toi", prompt)
    vues_canal: list[str] = []
    reponse: list[str] = []
    outils: list[str] = []
    historique = pieces.get("historique")
    if historique is None:
        historique = memoire.messages()
        pieces["historique"] = historique
    async for chunk in flux_cerveau(
        pieces["brain"],
        prompt,
        pieces["registre"],
        pieces["porte"],
        historique,
    ):
        canal_chunk = chunk.get("channel")
        if canal_chunk:
            vues_canal.append(canal_chunk)
        if canal_chunk == "tool":
            nom = chunk.get("tool") or "outil"
            if chunk.get("phase") == "call":
                harnais = _harnais(nom)
                question = question_d_outil(chunk)
                print(f"→ {harnais} : {question}", flush=True)
                ecrire_ligne_conversation(journal, f"→ {harnais}", question)
                outils.append(nom)
            elif chunk.get("phase") == "result":
                contenu = (chunk.get("content") or "").strip()
                if contenu and nom in NOM_HARNAIS_PAR_OUTIL:
                    harnais = _harnais(nom)
                    print(f"← {harnais} : {contenu}", flush=True)
                    ecrire_ligne_conversation(journal, f"← {harnais}", contenu)
            continue
        if chunk.get("delta"):
            reponse.append(chunk["delta"])
    canal = canal_porteur(vues_canal)
    texte = recoller_prononce(reponse)
    duree_ms = (time.monotonic() - t0) * 1000.0
    print(f"[{canal} {duree_ms:.0f} ms] {texte}", flush=True)
    if texte:
        ecrire_ligne_conversation(journal, "hyper-ambient", texte)
        memoire.retenir(prompt, texte, origine=canal, timestamp=time.monotonic())
        pieces["historique"] = memoire.messages()
    return {
        "canal": canal,
        "duree_ms": duree_ms,
        "texte": texte,
        "outils": outils,
    }


async def _annoncer_mandat(pieces: dict, mandat) -> None:
    from src.brain.mandat import phrase_arrivee

    ligne = phrase_arrivee(mandat)
    print(f"← {mandat.harnais} : {ligne}", flush=True)
    ecrire_ligne_conversation(
        pieces.get("journal"), f"← {mandat.harnais}", ligne,
    )
    pieces["mandats"].marquer_annonce(mandat.identifiant)


async def attendre_mandats(pieces: dict, delai_s: float = 70.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < delai_s:
        for mandat in list(pieces["mandats"].prets()):
            await _annoncer_mandat(pieces, mandat)
        if not pieces["mandats"].en_cours() and not pieces["mandats"].prets():
            return
        await asyncio.sleep(0.5)


async def veiller_mandats(pieces: dict, stop: asyncio.Event) -> None:
    try:
        while not stop.is_set():
            for mandat in list(pieces["mandats"].prets()):
                await _annoncer_mandat(pieces, mandat)
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        raise


async def boucle(argv: list[str]) -> None:
    _appliquer_env_boot()
    pieces = await monter_cerveau()
    pieces["memoire"] = MemoireConversation()
    pieces["historique"] = []
    pieces["journal"] = nouveau_fichier_conversation()
    print(f"conversation : {pieces['journal']}", flush=True)
    try:
        if argv:
            await jouer_tour_ecrit(" ".join(argv), pieces)
            await attendre_mandats(pieces)
            garde = phrase_garde(
                [m.harnais for m in pieces["mandats"].en_cours()]
            )
            if garde:
                print(garde, flush=True)
            return
        stop = asyncio.Event()
        veille = asyncio.create_task(veiller_mandats(pieces, stop))
        try:
            while True:
                try:
                    ligne = input("> ").strip()
                except EOFError:
                    break
                if not ligne or ligne in {":q", "quit", "exit"}:
                    break
                await jouer_tour_ecrit(ligne, pieces)
        finally:
            stop.set()
            veille.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await veille
    finally:
        client = pieces.get("client")
        if client is not None:
            await client.aclose()
        brain = pieces.get("brain")
        if brain is not None and hasattr(brain, "close"):
            await brain.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Tour écrit : routeur, outils, mandats — sans voix.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Une question : mode non interactif. Sans argument : boucle stdin.",
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    asyncio.run(boucle(args.question))


if __name__ == "__main__":
    main()
