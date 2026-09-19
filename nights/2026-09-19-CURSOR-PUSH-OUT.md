---
date: 2026-09-19
heure: ~20:04 Europe/Paris
type: out
lane: CURSOR-PUSH
cible: OC (deadline 20:50) + Claude (WRAP-SOIR)
auteur: Cursor (Grok 4.6) — session desktop, stop demandé
deadline: 20:50 Europe/Paris
branche: nuit/2026-08-27
---

# CURSOR OUT — stop + push — 19 sept 20:50

Thomas absent. Ordre : **stop, préparer le push, OUT `nights/` obligatoire**.
Cette session n'a **pas** codé de lane : reçu l'ordre d'arrêt ~20:00. Inventaire
à chaud (autres harnais encore en train d'écrire sur disque) puis **commit + push**.
`.env.local` **non touché**, déjà gitignoré. Aucune valeur de secret affichée ici.

L'OUT 20:05 (`[[2026-09-19-CURSOR-OUT]]`) inventoriait **sans** commit.
Celui-ci **exécute** le push (Thomas absent, deadline dure).

## Exclus du `git add`

| Chemin | Pourquoi |
|---|---|
| `.env` `.env.local` | secrets — déjà ignorés |
| `dev/scripts/_tmp_*.py` | scratch — déjà ignoré |
| `nights/**/.carte-secrete*.json` | cartes aveugles |
| `nights/**/.carte-reel*.json` | même famille |
| `nights/degustation-19/oreille/enregistrements/` | voix de Thomas |
| `dev/tests/test_remote_tts.py` | C5 incomplet : `src.mouth.remote_tts` **absent** |
| `logs/` `models/` | déjà ignorés |

WAV TTS de dégustation (pas les enregistrements oreille) : **inclus** (~15 Mo).

## Inclus

| Fichier | Lane |
|---|---|
| `dev/scripts/serve_hostagent.py` | C1 chargeur `.env.local` + C10 traces + **P0-2** `charger_carte_figee` + **C12** `register_calculator` |
| `dev/scripts/carte_figee.env` | P0-2 carte persistante (pas de secret) |
| `dev/tests/test_hostagent_env_local.py` `test_carte_figee.py` | C1 / P0-2 |
| `native/presence/app.py` `sante.py` | C2 bandeau + C10 PTT après WS |
| `dev/tests/test_health_sondes.py` `test_presence_sante.py` `test_presence_premier_tour.py` | C2 / C10 |
| `workers/night_health_vault_note/*` + BPMN | C2 sondes |
| `src/mouth/normalize.py` `magpie_tts.py` | C9 + nombres |
| `dev/tests/test_normalize_nombres.py` `test_mouth_magpie.py` | C9 |
| `native/hostagent/talk.py` `windows_audio.py` | C10 traces |
| `src/brain/local_prompt.py` `openai_compat.py` | C11 |
| `dev/tests/test_c11_identity.py` | C11 |
| `src/ears/jev_reflexe.py` `dev/tests/test_jev_reflexe.py` | C3 (**module**, branchement host-agent à confirmer live) |
| `src/brain/tools_web.py` `dev/tests/test_tools_web.py` | C4 : 200 vide SearXNG → repli |
| `.env.example` `requirements-extra.txt` | C4 clés vides + `ddgs` |
| `src/brain/tools_calculator.py` `dev/tests/test_tools_calculator.py` | C12 **branché** dans le registre |
| `src/i18n/` `dev/tests/test_c8_i18n.py` | C8 EN 0.1 (FR défaut) |
| `dev/scripts/veille_hf.py` `banc_oreille.py` + tests | veille + banc |
| `.gitignore` | `_tmp_*` · `.carte-secrete*` · `.carte-reel*` · enregistrements oreille |
| `nights/2026-09-19-*` + C2 png + `nights/degustation-19/` | notes + preuves |

## Lanes encore ouvertes

| Lane | État |
|---|---|
| **P0-1** copie `E:` | pas d'OUT |
| **C5** TTS distant | test orphelin **exclu** |
| **WIRE** JeV + identité + hotwords | hotwords dans `carte_figee.env` ; JeV/id à confirmer live |
| Bug 1er tour | encore ouvert (C13 pythonw) |
| C1 live | chargeur env **fait** ; tour outil **non** prouvé ici |
| C2 live | coupe HTTP `:1` prouvée ; pont `:8765` **non** tué ; **voix non branchée** |
| P0-2 live | fichier carte **fait** ; reboot réel **non** rejoué ici |

## Ne pas casser à la reprise

Stack live : `mother-core-dev`, llama-server `:8080` Granite, host-agent `:8001` via `/tmp/relance_hostagent.sh` (la carte disque existe maintenant dans `dev/scripts/carte_figee.env`), Magpie `:8092` CUDA. Pas de `docker compose up` / recreate.

## Done cette session

| Attendu | Statut |
|---|---|
| Stop | oui |
| OUT `nights/` | ce fichier |
| Commit | oui (Thomas absent, deadline 20:50) |
| Push | `nuit/2026-08-27` → origin |
| Secrets | aucun `.env.local`, aucune `.carte-secrete`, aucun WAV oreille |

## Preuve git

```
(à coller après push : hash + URL)
```
