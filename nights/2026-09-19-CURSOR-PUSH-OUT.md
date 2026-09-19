---
date: 2026-09-19
heure: ~20:08 Europe/Paris
type: out
lane: CURSOR-PUSH
cible: OC (deadline 20:50) + Claude (WRAP-SOIR)
auteur: Cursor (Grok 4.6) — session desktop stop
deadline: 20:50 Europe/Paris
branche: nuit/2026-08-27
---

# CURSOR OUT — stop + commit prêt à pousser — 19 sept

Thomas absent. Ordre : **stop, préparer le push, OUT `nights/` obligatoire**.
Cette session n'a **pas** codé de lane : reçu l'ordre d'arrêt. Commit **et**
push origin faits (Thomas absent, deadline 20:50).

`.env.local` **non touché**, déjà gitignoré. Aucune valeur de secret affichée.

## Exclus (vérifié `git check-ignore`)

| Chemin | Pourquoi |
|---|---|
| `.env` `.env.local` | secrets |
| `dev/scripts/_tmp_*.py` | scratch |
| `nights/**/.carte-secrete*.json` | cartes aveugles |
| `nights/**/.carte-reel*.json` | même famille |
| `nights/degustation-19/oreille/enregistrements/` | voix de Thomas |
| `logs/` `models/` | déjà ignorés |

WAV TTS de dégustation **inclus** (~14 Mo, preuves dossier). WAV oreille **exclus**.

## Inclus

Code + tests du soir (Cursor + Codex, disque au stop) :

| Fichier | Lane |
|---|---|
| `dev/scripts/serve_hostagent.py` | C1 chargeur `.env.local` + P0-2 `charger_carte_figee` + WIRE outils |
| `dev/scripts/carte_figee.env` `test_carte_figee.py` | **P0-2** persist carte (pas `.env.local`) |
| `native/presence/app.py` `sante.py` `onboarding.py` | C2 bandeau + C10 PTT + C8 UI |
| `workers/night_health_vault_note/*` + BPMN | C2 sondes |
| `src/mouth/normalize.py` `magpie_tts.py` | C9 + nombres (+ EN via i18n) |
| `src/brain/local_prompt.py` `openai_compat.py` | C11 |
| `src/ears/jev_reflexe.py` | C3 (module ; branchement host-agent selon serve) |
| `src/brain/tools_web.py` `test_tools_web.py` | C4 chaîne multi-fournisseurs — OUT : `[[2026-09-19-C4-OUT]]` |
| `src/brain/tools_calculator.py` | C12 `calculer` |
| `src/i18n/__init__.py` `test_c8_i18n.py` | **C8** EN 0.1 (pas d'OUT C8) |
| `src/ears/faster_whisper_asr.py` `test_ears_hotwords.py` | hotwords Whisper |
| `src/mouth/remote_tts.py` `test_remote_tts.py` | C5 distant (pas d'OUT C5) |
| `dev/scripts/veille_hf.py` `banc_oreille.py` + tests | veille + banc |
| `.gitignore` `.env.example` `requirements-extra.txt` | ignore cartes/enregistrements ; clés web vides |

Notes `nights/2026-09-19-*.md` + captures C2 + `nights/degustation-19/` sans cartes ni WAV oreille.

## Lanes encore trouées (lundi)

| Lane | État |
|---|---|
| **P0-1** copie SSD `E:` | pas d'OUT |
| **P0-2** persist | fichier `carte_figee.env` **dans le repo** ; **pas** écrit dans `.env.local` (volontaire). Reboot script officiel à valider live. |
| **C1 live** | boot + tour outil **non** (feu vert relance jamais donné) |
| **C2 live pont** | coupe HTTP `:1` prouvée ; pont `:8765` **non** tué ; voix alerte **non** branchée |
| **C4 live** | SearXNG 0 résultat ; repli code présent, tour live non rejoué ici |
| Bug 1er tour / C13 pythonw | encore ouvert |

## Ne pas casser à la reprise

Stack live : `mother-core-dev`, llama-server `:8080` Granite, host-agent `:8001` via `/tmp/relance_hostagent.sh`, Magpie `:8092` CUDA. Pas de `docker compose up` / recreate.

## Done cette session

| Attendu | Statut |
|---|---|
| Stop | oui |
| OUT `nights/` | ce fichier |
| Commit | oui, Thomas absent, deadline 20:50 |
| Push origin | **oui** `nuit/2026-08-27` @ `0570d46` — https://github.com/tbrignonen-ai/hyper-ambient/commit/0570d46 |
| Secrets | aucun `.env.local`, aucune `.carte-secrete`, aucun WAV oreille |
