---
date: 2026-09-19
type: dossier-bgb
auteur: Claude (MOTHER-PLAN-19) — suggestions ; **Thomas remplit**
source: D:\BGB Training\BGB_BC02_Dossier_technique_a_completer.docx
---

# Suggestions pour les cases du dossier BC02

Règle : n'écrire que ce qui est vrai **et démontrable lundi**. `[P]` = à prouver avant d'écrire.

## À trancher par Thomas (avant de remplir)
1. **« Plateformes no code/low code utilisées »** — MOTHER est du code. Élément low-code réel : **Camunda 8
   (BPMN modélisé + worker)**. Proposition : *« Camunda 8 (orchestration BPMN) ; MOTHER = composant IA local
   intégré comme service »*. Présenter le projet comme **solution d'automatisation IA orchestrée**, pas comme appli codée.
   Si le jury attend Make/n8n/Bubble : assumer l'écart et le justifier (local, RGPD, sobriété) en une phrase.
2. **« Cas traité »** : un cas d'organisation, pas « mon projet perso ». Ex. : *assistant vocal mains libres pour
   une petite équipe tech (supervision, recherche, délégation à des agents IA), données qui restent sur le poste*.
3. Seul ou groupe : individuel → « contributions personnelles » = tout, dire ce qui a été **délégué à des agents IA** et comment c'est contrôlé (c'est un argument, pas une faiblesse).

## Section par section

| § | Case | Suggestion (ancre réelle) |
|---|---|---|
| 1 | Contexte (5–10 l.) | Besoin : piloter outils et agents IA à la voix, sans cloud par défaut. Contraintes : FR, Windows, 1 GPU grand public, RGPD. |
| 1.1 | Schéma C4 (≥4 composants) | Presence UI · host-agent (oreille / cerveau / voix) · LLM local `:8090` · ponts Codex/Claude `:8765/:8766` · SearXNG · Camunda + worker · coffre Obsidian. Schéma produit par l'annexe (Codex). |
| 1.2 | Justification (3–6 l.) | Local d'abord (confidentialité, latence, coût) ; escalade distante seulement sur demande via outils ; BPMN pour rendre les automatisations lisibles par un non-dev. |
| 2.1 | Table interop | 1 ligne/système : ponts IA (HTTP JSON, jeton Bearer), SearXNG (HTTP JSON, réseau local), Camunda (REST v2), Obsidian (fichiers Markdown), GitHub (API, retours usagers `[P]`). |
| 2.2 | 2 points critiques | (a) pont distant indisponible → repli local + alerte (démo C2) ; (b) note Obsidian écrite puis relue avant validation (déjà dans le worker). |
| 3.1 | Risques (≥3 catégories) | Accès : jetons des ponts (`.env.local` hors git) · API : ponts en localhost uniquement `[P]` · Stockage : audio non conservé `[P]` · Tiers : réponses d'un LLM distant (outils classés `danger=read`, porte `GATE_MODE`). |
| 3.2 | Méthode | Grille probabilité × impact simple + OWASP Top 10 LLM (injection de prompt via outils). |
| 4.1 | T1–T7 | T1 dialogue vocal simple · T2 escalade vers Claude (C1) · T3 onboarding 3 étapes · T4 suites pytest (collées) · T5 registre outils sans/avec jetons (tests existants `test_outils_voix.py`) · T6 contraste + clavier Presence `[P]` · T7 délai avant premier son `[P]` mesuré. |
| 4.2 | Analyse | Vrais bugs corrigés et datés : hachurage audio (rééchantillonnage, 6 sept), accent britannique → voix FR native (8 sept), interruption au bouton (15 sept), outils non chargés (19 sept, C1). |
| 5.1 | Suivi | Health-check BPMN périodique → note Obsidian ; lecture quotidienne des retours. |
| 5.2 | 3 volets | RGPD : traitement local, pas de stockage audio `[P]` · Sobriété : modèles quantifiés, escalade distante seulement à la demande · Accessibilité : usage 100 % voix + texte à l'écran `[P]`. |
| 5.3 | Retours d'usage | Bouton feedback → issue GitHub, lue 1×/jour `[P — existe ?]`. Sinon ne pas l'écrire. |
| 6.1 | Roadmap RICE | Mac · EN/ES · Hyper-Ambient-XL (~20 Go VRAM) · routeur déterministe local (NOTE-JEV). |
| 6.2 | Continuité | Branches git, tests avant fusion, retour arrière = commit précédent + relance du service. |
| 7.1 | Doc | Extrait d'un ADR ou de `SKU10-PANNE` ; hébergement : dépôt public GitHub + coffre Obsidian. |
| 7.2 | Versions | Tirées de `git log` (Codex prépare). |
| 8.1 | Écrans | Captures Presence existantes (`nights/2026-09-18-cursor-ui-*.png`) + bandeau d'alerte C2. |
| 8.2 | 2 profils | (1) utilisateur mains libres (voix seule) ; (2) utilisateur qui installe / configure (assistant 3 étapes, clavier). Principes : contrastes, navigation clavier, alternative texte à la voix. |
| 9.1 | ≥3 flux | voix→texte→réponse→voix (rien ne sort du poste) ; question→escalade distante→réponse ; santé→BPMN→note Obsidian. |
| 10.1 | Alerte + reprise | **Démo C2** : pont coupé → bandeau + phrase + note → relance → retour vert. Lien §3 : risque « service tiers indisponible ». |
| 10.2 | Messages | Reprendre mot pour mot les messages de l'OUT C2. |
| 11.1 | Service tiers | **Démo C1** : Claude/Codex via ponts HTTP authentifiés, jetons en `.env.local` jamais committés ; SearXNG pour la recherche. |
| 11.2 | Vérifs & impacts | Tests registre outils ; appels distants seulement sur décision de l'outil (pas à chaque tour) → sobriété. |

## Annexe 15–30 p.
Plan détaillé et règle de sourçage : `2026-09-19-BRIEF-CODEX.md` (lane X1). Claude relit avant Thomas.

## Soutenance (rappel du guide)
15 min + 10 min de questions ; démos obligatoires = **alerte + reprise** et **service tiers**. Un seul fil :
profil 1 parle → escalade Claude (C1) → je coupe le pont → alerte (C2) → relance → retour. Plan B = captures.
