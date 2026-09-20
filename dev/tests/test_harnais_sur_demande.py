"""Les harnais ne s'appellent que sur demande explicite.

Mesure en conditions reelles le 2026-09-20, mains libres actif :

    TRANSCRIPT 'MOTHER Codex Camunda'          <- hallucination de Whisper
    OUTIL : ask_codex
    ask_codex: echec annonce par le pont (delai depasse)
    MOUTH : premier audio apres 39029 ms       <- 39 secondes de silence

Whisper avait recrache la liste `EARS_HOTWORDS` elle-meme : en soufflant ces
mots au moteur, on en a fait un aimant a hallucinations. Le cerveau a vu
« Codex » et a appelle le harnais, qui a expire.

Consigne de l'utilisateur : « elle ne doit pas appeler les harnais sans demande
explicite ». Un nom d'outil qui traine dans une transcription n'est pas une
demande.
"""
from __future__ import annotations

import pytest

from src.brain.harnais import harnais_demande


@pytest.mark.parametrize("phrase", [
    "demande a Codex ce qu'il pense de ce fichier",
    "demande à Claude de relire le code",
    "peux-tu demander a Codex son avis ?",
    "interroge Claude la-dessus",
    "pose la question a Codex",
    "ask Codex about this file",
])
def test_demande_explicite_autorise(phrase):
    assert harnais_demande(phrase)


@pytest.mark.parametrize("phrase", [
    "MOTHER Codex Camunda",                       # l'hallucination reelle
    "Codex",
    "on a installe Codex et Claude hier",
    "je parlais de Codex tout a l'heure",
    "Non, mais il ne faut pas appeler Codex.",     # refus explicite !
    "bonjour",
    "",
])
def test_simple_mention_ne_suffit_pas(phrase):
    assert not harnais_demande(phrase)
