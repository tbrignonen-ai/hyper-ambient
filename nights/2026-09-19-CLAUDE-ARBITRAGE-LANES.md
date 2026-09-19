---
date: 2026-09-19
type: arbitrage
auteur: Claude (lead technique)
pour: OC
---

# Arbitrage lanes pendant la dégustation

## 1. GO maintenant
- **C1** (Cursor) — la cause racine + le correctif portent sur la **propagation de `.env.local`**, quel que soit le modèle choisi. Pas de retour arrière avec la carte figée.
  Limite : **aucun changement de valeur** `MOUTH_*` / `EARS_*` / `MODEL` / `BRAIN_*` (c'est la carte qui les fixera).
- **C2** (Cursor, run séparé) — alerte + reprise, indépendant des modèles.
- **X1** (Codex, docs seuls) — sections modèles marquées `[CARTE EN COURS]`, sans nom de modèle figé.

## 2. ATTENDRE la carte figée
C3 (JeV), C4 (web), C5 (TTS distant), C6 (onboarding), C7 (natif Windows). Leurs briefs seront écrits après la carte.

## 3. Ordre, fichiers, risques
- Fichiers disjoints : C1 = `dev/scripts/serve_hostagent.py`, `src/brain/tools*.py`, lancement host-agent, tests associés. C2 = `native/presence/*`, `workers/*`, `resources/bpmn/*`, tests associés. X1 = `nights/…ANNEXE…md` uniquement.
  **Personne ne touche** `nights/degustation-19/`, `dev/scripts/veille_hf.py`, `.env.local` (lecture seule pour C1).
- **Risque principal = le GPU (12 Go), partagé avec la dégustation.** C1 et C2 ne **relancent pas** le host-agent ni `:8090`, et ne chargent aucun modèle **sans feu vert de Claude**.
  Le diagnostic, les tests et le correctif sont libres ; la preuve live (relance + tour réel) se fait dans un créneau que je donne.
- C2 ne modifie pas `serve_hostagent.py` : s'il faut une annonce vocale, le besoin est écrit dans l'OUT et j'arbitre.

## 4. Consigne OC
Lance C1 + C2 (Cursor, 2 runs) + X1 (Codex) maintenant. Interdit : relancer le host-agent ou `:8090`, charger un modèle GPU, modifier une valeur de modèle dans l'env, sans feu vert Claude.
