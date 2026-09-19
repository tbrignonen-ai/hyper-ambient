---
date: 2026-09-19
type: brief
cible: Codex (overflow — docs seuls)
auteur: Claude (MOTHER-PLAN-19)
plan: "[[2026-09-19-CLAUDE-PLAN-TECH]]"
---

# BRIEF Codex — X1 Annexe technique Hyper Ambient (15–30 p.)

**Aucun fichier de code.** Un seul fichier écrit : `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md`.
Lecture libre : repo (`ARCHITECTURE.md`, `STACK.md`, `STATUS.md`, `src/`, `native/`, `workers/`, `resources/bpmn/`,
`dev/tests/`, `dev/measurements/`, `nights/`), `git log`. Docs BGB : `D:\BGB Training\BGB_BC02_*.docx`.
Cadre des cases : `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md`.

## Règle de vérité (non négociable)
Chaque affirmation technique porte sa source : `fichier:ligne`, hash de commit, ou note `nights/…`.
Pas de source → **[À PROUVER]**. Aucun chiffre inventé (latences, VRAM, nb de tests) : seulement ceux
mesurés dans le dépôt/notes. Aucun secret, token ou URL privée.

## Plan imposé (≈ pages) — calé sur les sections 1–11 du dossier BGB
1. Résumé exécutif + périmètre (FR, Windows, local-first, clé-en-main) — 1 p.
2. Architecture C4 niveaux 1–2 (Mermaid) : Presence UI, host-agent (EARS/BRAIN/MOUTH), LLM local `:8090`, ponts `:8765/:8766`, SearXNG, Camunda + worker, coffre Obsidian — 3 p. (§1)
3. Table d'interopérabilité (système, sens, protocole, format, auth) + 2 points critiques de sync — 2 p. (§2)
4. Flux de données (≥3) : voix→texte→décision→voix ; escalade distante ; health→note Obsidian ; règles RGPD — 3 p. (§9)
5. **Automatisation IA** (angle BC02) : ex-crons de nuit, BPMN Camunda health→note, coffre `nights/` comme bus de coordination multi-agents (OC/Cursor/Codex/Claude), onboarding assisté, porte `GATE_MODE`, outils `ask_*` classés `danger=read` — 3 p. (§11)
6. Sécurité : tableau risques (accès/droits, exposition API, stockage, services tiers) + mesures + référence (RGPD / ANSSI / OWASP LLM Top 10) — 2–3 p. (§3)
7. Plan de tests : inventaire des suites pytest réelles, T1–T7 ; résultats uniquement s'ils sont collés dans un OUT — 2 p. (§4)
8. Alertes & reprise : `2026-09-18-SKU10-PANNE.md` + OUT C2 quand disponible — 2 p. (§10)
9. Qualité/conformité continue : RGPD, sobriété (local d'abord, escalade rare, modèles quantifiés), accessibilité — 2 p. (§5)
10. Feuille de route RICE : Mac, EN/ES, Hyper-Ambient-XL (~20 Go VRAM), routeur déterministe (voir `2026-09-19-NOTE-JEV.md`) — 1–2 p. (§6)
11. Documentation & traçabilité : ADR, `nights/`, journal de versions tiré de `git log` — 2 p. (§7)
12. Annexes : glossaire, captures existantes `nights/*.png` — 1–2 p.

## OUT
Le fichier annexe, avec en tête la liste « [À PROUVER] restants » pour arbitrage Claude/Thomas.
