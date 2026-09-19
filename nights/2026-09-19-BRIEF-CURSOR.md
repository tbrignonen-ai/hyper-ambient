---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6 xhigh fast)
auteur: Claude (MOTHER-PLAN-19)
plan: "[[2026-09-19-CLAUDE-PLAN-TECH]]"
---

# BRIEF Cursor — 19 sept — 2 lanes, fichiers disjoints

Workspace : `D:\BGB Training\MOTHER-dev` · branche courante `nuit/2026-08-27` · FR.
But : rendre démontrables **en direct lundi** les deux démos obligatoires du jury BGB :
**service tiers en fonctionnement** (C1) et **alerte déclenchée + reprise** (C2).

Règles communes : TDD (test rouge **vu** puis vert, sorties collées) · cause racine avant correctif ·
pas de `docker compose up`/recreate · pas de config Hermes · **aucune valeur de secret** affichée
(dire « présent/absent/vide » seulement) · **pas de commit** (Thomas valide) · ne touche **aucun** fichier hors de ta liste.

---

## C1 — Outils câblés au host-agent (P0, en premier)

**Symptôme (OC, boot du jour)** : `OUTILS: aucun backend configure — tour de parole sans outil`
(`dev/scripts/serve_hostagent.py:396`). Ponts Codex `:8765` et Claude `:8766` répondent PONG.

**Code concerné** : `construire_registre()` (`serve_hostagent.py:102-160`) n'enregistre un outil que si
`CODEX_BRIDGE_TOKEN` / `CLI_BRIDGE_TOKEN` / `SEARXNG_URL` (ou `TAVILY_API_KEY`) sont non vides dans l'env du process.

**Étapes**
1. **Diagnostic d'abord** : dans quel process/contexte tourne le host-agent (conteneur `mother-core-dev` ou hôte) ?
   Comment reçoit-il son env ? Les 3 variables sont-elles présentes/vides à l'exécution ? Piste connue :
   `.env.local` en fins de ligne mixtes CRLF/LF (valeur avec `\r` final → token faux, ou ligne ignorée).
   Consigne la cause racine prouvée dans l'OUT avant de corriger.
2. Test rouge qui reproduit la cause (ex. chargement d'env avec `\r`, ou variable absente au lancement).
3. Correctif minimal à la racine (chargement/propagation d'env ou script de lancement), pas un contournement codé en dur.
4. Relance du host-agent (dans ton périmètre, **sans** recreate de conteneur) → log boot attendu :
   `OUTILS: ask_codex, ask_claude, … — porte en mode …`.
5. **Preuve bout-en-bout** : 1 tour réel (texte ou voix) déclenchant `ask_claude` ou `ask_codex` ; log de l'appel
   (outil, durée, statut HTTP) + réponse restituée. Réutiliser `dev/scripts/verify_hostagent_loop.py` si adapté.

**Fichiers possédés** : `dev/scripts/serve_hostagent.py`, `src/brain/tools.py`, `src/brain/tools_cli.py`,
`src/brain/tools_codex.py`, `src/brain/tools_web.py`, script(s) de lancement du host-agent,
`dev/tests/test_tools*.py`, `dev/tests/test_outils_voix.py`, `dev/tests/test_hostagent_*.py`.
**Interdit** : `src/brain/tools_muse.py` (Muse OUT, ne pas réactiver), `native/presence/*`, `workers/*`.

**OUT** : `nights/2026-09-19-C1-OUTILS.md` — cause racine, diff résumé, test rouge→vert (sortie pytest),
log boot, log du tour avec outil. Done = ces 4 preuves collées.

---

## C2 — Alerte visible + reprise (P0 bis)

**Existant à réutiliser** : process Camunda `resources/bpmn/night_health_vault_note.bpmn` + worker stdlib
`workers/night_health_vault_note/` (`health-check` → `vault-note` écrit `{nightDate}-HEALTH.md`, statut UP/DEGRADED).
Aujourd'hui il ne sonde que la topologie Camunda. Script de reprise connu : `nights/2026-09-18-SKU10-PANNE.md`.

**Cible démo (ce que le jury voit)** : j'arrête volontairement un composant (ex. pont Codex `:8765`) →
1. le health-check le détecte (`DEGRADED`, composant nommé) ;
2. **alerte** sur 3 canaux : bandeau dans Presence (texte clair, contrasté, lisible au lecteur d'écran),
   phrase parlée courte par MOTHER (« Le pont vers Codex ne répond plus, je continue en local. »), note Obsidian HEALTH ;
3. **reprise** : relance du composant → retour `UP` → bandeau disparu + phrase « Pont Codex rétabli. »

**Étapes**
1. Vérifier si Camunda (`:8088`) tourne ; si non, **ne pas le lancer via compose** — le noter et prévoir un
   mode dégradé : sonde directe des endpoints (ponts, host-agent `:8001`, LLM `:8090`) depuis les handlers, en stdlib.
2. Tests rouges : handler health-check qui classe DEGRADED quand un endpoint ne répond pas ; bandeau Presence
   qui apparaît/disparaît selon l'état (test sans GUI réelle, sur le modèle de `dev/tests/test_presence_onboarding.py`).
3. Implémenter ; messages d'erreur en FR simple, sans jargon (ils iront tels quels dans le dossier §10.2).
4. Démo réelle : couper → alerte → relancer → retour. Captures `nights/2026-09-19-c2-*.png`.

**Fichiers possédés** : `native/presence/*`, `dev/tests/test_presence_*.py`, `workers/night_health_vault_note/*`,
`resources/bpmn/*`, nouveaux tests `dev/tests/test_health_*.py`.
**Interdit** : tout fichier C1. L'annonce vocale passe par un point d'entrée **existant** du host-agent ;
s'il n'y en a pas, **ne pas modifier `serve_hostagent.py`** : écrire le besoin dans l'OUT, Claude arbitre.

**OUT** : `nights/2026-09-19-C2-ALERTE.md` — composants sondés, 3 messages exacts affichés/dits,
sorties pytest rouge→vert, captures avant/pendant/après, durées détection→alerte et relance→retour.

---

## Ordre et parallélisme
C1 d'abord. C2 peut démarrer en parallèle **dans un run séparé** (arbres disjoints). Blocage
(3 essais ratés) → stop + OUT avec ce qui bloque — ne pas élargir le périmètre.
