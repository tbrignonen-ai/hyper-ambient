---
date: 2026-09-19
heure: ~20:04 Europe/Paris
type: out
lane: CURSOR-WRAP
cible: OC (push 20:50) + Claude (WRAP-SOIR)
auteur: Cursor (Grok 4.6) — session desktop, stop demandé
deadline: 20:50 Europe/Paris
branche: nuit/2026-08-27 @ 33b423c
---

# CURSOR OUT — stop + préparation push — 19 sept 20:04

Thomas absent. Ordre reçu uniquement : **stop, préparer le push, OUT `nights/` obligatoire**.
Cette session n'a **pas** codé de lane. **Pas de commit. Pas de push.** (règle Thomas + OC à 20:50.)
`.env.local` **non touché**, déjà gitignoré. Aucune valeur de secret affichée ici.

Un autre OUT (`[[2026-09-19-CURSOR-PUSH-OUT]]`) annonce commit+push : **ne pas le suivre depuis cette session**. Runbook opératoire : `[[2026-09-19-PUSH]]`.

## Preuve git (commandes exécutées ~20:04)

```
branche  * nuit/2026-08-27 33b423c [origin/nuit/2026-08-27]
HEAD     docs(nights): PUSH.md URLs finales 18 sept
gitignore .env / .env.local / _tmp_*.py / .carte-secrete* / .carte-reel* / enregistrements/
secrets   aucune chaîne sk- / ghp_ / hf_ dans nights/*.md
check-ignore OK : .env · .env.local · _tmp_hf_oreille.py · 6× .carte-secrete*.json
```

C4 mesuré dans `mother-core-dev` (pas de recreate) : `test_tools_web.py` **14 passed**.
C12 : `test_tools_calculator.py` **6 passed**.
C8 : `test_c8_i18n.py` **ERROR collection** (`No module named 'src.i18n'`).
C5 : `test_remote_tts.py` présent, `src/mouth/remote_tts.py` **absent**.

## Mines à exclure du `git add`

Un `git add dev/tests/test_*.py` embarquerait deux tests **rouges à la collecte** :

| Fichier | Pourquoi exclure |
|---|---|
| `dev/tests/test_c8_i18n.py` | `src.i18n` n'existe pas — casse `pytest dev/tests` |
| `dev/tests/test_remote_tts.py` | `src.mouth.remote_tts` n'existe pas |

## À inclure

### Code + tests déjà sur disque

| Fichier | Lane | Note |
|---|---|---|
| `dev/scripts/serve_hostagent.py` | C1 + P0-2 + C10 | chargeur `.env.local` (outils) + `charger_carte_figee` |
| `dev/scripts/carte_figee.env` | **P0-2** | Granite / Whisper large-v3 int8 / Magpie Sofia CUDA — **aucun secret** |
| `dev/tests/test_hostagent_env_local.py` `test_carte_figee.py` | C1 / P0-2 | |
| `native/presence/app.py` `sante.py` | C2 + C10 | bandeau + PTT après WS |
| `dev/tests/test_health_sondes.py` `test_presence_sante.py` `test_presence_premier_tour.py` | C2 / C10 | |
| `workers/night_health_vault_note/*` + BPMN | C2 sondes | |
| `src/mouth/normalize.py` `magpie_tts.py` | C9 + nombres | |
| `dev/tests/test_normalize_nombres.py` `test_mouth_magpie.py` | C9 | |
| `native/hostagent/talk.py` `windows_audio.py` | C10 traces | |
| `src/brain/local_prompt.py` `openai_compat.py` | C11 | **pas branché** live |
| `dev/tests/test_c11_identity.py` | C11 | |
| `src/ears/jev_reflexe.py` `dev/tests/test_jev_reflexe.py` | C3 | **pas branché** au host-agent |
| `src/brain/tools_web.py` `dev/tests/test_tools_web.py` | C4 | chaîne SearXNG→ddgs→Tavily→Brave→Exa→Jina→Serper ; 200 vide = repli ; **pas d'OUT C4** |
| `.env.example` | C4 | noms de clés vides seulement |
| `requirements-extra.txt` | C4 | `ddgs>=9.0` (import paresseux) |
| `src/brain/tools_calculator.py` `dev/tests/test_tools_calculator.py` | C12 | **pas branché** au host-agent ; pas d'OUT |
| `dev/scripts/veille_hf.py` `banc_oreille.py` + tests | veille + banc | |
| `.gitignore` | wrap | `_tmp_*` · cartes · enregistrements oreille |

### Notes `nights/` 19 sept

Tous les `nights/2026-09-19-*.md` + captures C2 + `nights/degustation-19/` **sans** cartes secrètes ni WAV oreille (gitignorés). WAV TTS ~15 Mo : preuves dossier, **inclus** par défaut.

## EXCLURE

| Chemin | Pourquoi |
|---|---|
| `.env` `.env.local` | secrets — déjà ignorés |
| `dev/scripts/_tmp_*.py` | scratch — ignoré |
| `nights/**/.carte-secrete*.json` `.carte-reel*.json` | cartes aveugles |
| `nights/degustation-19/oreille/enregistrements/` | voix de Thomas |
| `dev/tests/test_c8_i18n.py` | C8 incomplet |
| `dev/tests/test_remote_tts.py` | C5 incomplet |
| `logs/` `models/` | déjà ignorés |

## Lanes au snapshot 20:04

| Lane | OUT | Code | Live |
|---|---|---|---|
| C1 outils | `C1-OUTILS.md` | chargeur env **fait** | boot + tour outil **non** |
| C2 alerte | `C2-ALERTE.md` | bandeau + sondes **faits** | pont live `:8765` **non** tué ; voix alerte **non branchée** |
| C3 JeV | `C3-OUT.md` | module **fait** | **pas branché** |
| C4 web | **ABSENT** | chaîne + 14 tests verts | SearXNG 0 résultat live ; pas de preuve bout-en-bout |
| C5 TTS distant | **ABSENT** | test seul, **module absent** | **exclure** |
| C8 EN 0.1 | **ABSENT** | test seul, **`src.i18n` absent** | **exclure** |
| C9 Magpie Sofia | `C9-MAGPIE-OUT.md` | backend + nombres **faits** | CUDA ttfa **1341 ms** |
| C10 1er tour | `C10-PREMIER-TOUR-OUT.md` | PTT après WS **fait** | bug 1er tour **ouvert** (C13 pythonw) |
| C11 identité | `C11-OUT.md` | prompt **fait** | **pas branché** |
| C12 calculer | **ABSENT** | module + 6 tests | **pas branché** |
| P0-1 copie `E:` | **ABSENT** | Codex encore en copie | ne rien supprimer sur `D:` |
| **P0-2 persist carte** | **ABSENT** | `carte_figee.env` + chargeur **faits** (`.env.local` non modifié) | host-agent live tourne encore via `/tmp/relance_hostagent.sh` — **relance host-agent requise** pour activer |
| WIRE JeV+id+hotwords | **ABSENT** | hotwords dans `carte_figee.env` ; JeV/id sur disque, **non branchés** | |

Si C4-OUT / P0-1 / P0-2-ENV / WIRE arrivent avant 20:50, OC les ajoute. Ne pas attendre. Ne pas ajouter C8/C5 tant que les modules manquent.

## Ne pas casser à la reprise

Stack live : `mother-core-dev`, llama-server `:8080` Granite, host-agent `:8001` via `/tmp/relance_hostagent.sh`, Magpie `:8092` CUDA. Pas de `docker compose up` / recreate.

P0-2 fichier prêt, **pas encore le process live**. Sans relance host-agent (sans recreate), un reboot scripté peut encore retomber sur Pocket/Estelle + MiniCPM si `relancer_routeur.sh` ignore `carte_figee.env`.

## Done cette session

| Attendu | Statut |
|---|---|
| Stop | oui |
| OUT `nights/` | ce fichier |
| Inventaire push | `[[2026-09-19-PUSH]]` |
| Commit | **non** |
| Push | **non** (OC 20:50) |
