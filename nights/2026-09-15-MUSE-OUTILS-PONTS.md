---
date: 2026-09-15
heure: ~21:30 Europe/Paris
type: out
auteur: Muse (spark, high-level)
cible: Thomas + Claude (lead voix)
statut: livré — ponts vérifiés côté code, backend Muse smoke, live intact
hermes: OFF (registre voix) — chemin pont vérifié, Hermes2/SAWB intacts
related:
  - "[[2026-09-13-MUSE-CONNEXIONS]]"
  - "[[2026-09-14-CODEX-ANALYSE-SEANCE]]"
---

# Outils — ponts Codex / Claude / Muse / Hermes (15 sept, soir)

Note : `nights/2026-09-15-ASSIGN-MUSE-OUTILS.md` n'existe pas dans le repo.
Mission exécutée depuis le brief chat + les deux notes lues (13 + 14 sept).

Règle tenue : **rien touché** au live — ni `.env.local`, ni host-agent,
ni conteneur, ni voix/TTS/Presence, ni `mother-core` recreate.
Ce sandbox WSL ne voit ni le host Windows (interop bloquée) ni Docker :
tout ce qui est Windows/conteneur est vérifié par le code + tests,
pas par smoke direct. Pas de bluff ci-dessous.

## Fait

1. **Tests outils + ponts : 137 passed.**
   `test_tools_codex/cli/muse/web`, `test_codex_bridge`, `test_clibridge`,
   `test_outils_voix`, `test_tavily_mock_only` — venv éphémère `/tmp`
   (pytest + httpx + numpy + starlette), 3,1 s. Dont 4 tests Hermes :
   argv déclaré, absent-du-PATH => refus sans processus, binaire présent
   mais non armé => refus, `CLI_BRIDGE_HERMES=1` => autorisé.
2. **Backend `ask_muse` (pont Muse WSL) : health + smoke partiel.**
   `/health` => 200 x2, `{"ok": true, "muse": "Muse Code 1.3.0",
   "model": "muse-spark-1.3"}`. `/ask` => 502 propre quand `muse exec`
   échoue (passthrough d'erreur conforme au contrat `{"text": ...}`
   attendu par `tools_muse.py`). `muse exec` lui-même impossible ici :
   `~/.config/muse` illisible dans ce sandbox (limite sandbox, pas bug
   produit — chaîne exec déjà prouvée le 13 sept : HTTP 200 en 23,8 s
   depuis le conteneur). Pont `/tmp` arrêté après le smoke : **aucun
   processus laissé**, aucun conflit avec le `start.sh` officiel.
3. **Contrats ponts relus dans le code (pour les start Windows) :**
   - Codex : `0.0.0.0:8765`, `POST /ask {"question"}`, Bearer
     `CODEX_BRIDGE_TOKEN` (pont fermé sans jeton).
   - Claude : `0.0.0.0:8766`, `POST /ask {"question","agent"}`,
     Bearer `CLI_BRIDGE_TOKEN`.
   - Muse : `POST {MUSE_BRIDGE_URL}/ask {"instruction"}` => `{"text"}`.
   - URLs Codex/Claude déjà en défaut dans le code
     (`host.docker.internal:8765|8766/ask`, idem `relancer_routeur.sh`) :
     **seuls les 2 jetons + `MUSE_BRIDGE_URL` manquent dans `.env.local`.**
4. **Hermes interconnecté sans toucher SAWB.**
   - `ask_hermes` reste **interdit** au registre voix (invariant
     `serve_hostagent.verifier_registre`, testé) : l'interconnexion est
     au niveau pont, pas voix.
   - Hermes2 vivant ce jour (autostart OK 12:54 et 18:12 : gateway,
     dashboard, lightpanda Up). `muse_bridge.py` local **identique**
     à `/mnt/e/AI/Hermes2/tools/muse_bridge.py` (pas de divergence).
     Hermes2 compose ne référence pas le pont (usage à la demande) :
     le redémarrer ne casse rien côté Hermes2.
   - 0 GPU / 0 VRAM / 0 modèle chargé par cette mission. SAWB untouched.

## Bloqué (sandbox, pas produit)

| Blocage | Cause | Preuve que c'est le sandbox |
|---|---|---|
| Smoke 8765/8766/8080, PONG `codex`/`claude` | pas d'interop Windows (`cmd.exe`/`powershell.exe` => vsock error), pas de `docker.sock`, host IP => 000 | sorties `000` directes, sans proxy |
| Smoke `muse exec` complet | `~/.config/muse` : Permission denied | `ls` + message `muse` explicite |
| Inscription `ask_*` au registre live | exige relance host-agent = touche le live (interdit, tests voix en cours) | `relancer_routeur.sh` exporte `.env.local` au relaunch |
| `web_search` smoke | SearXNG injoignable d'ici ; déjà OK au live — non retesté, comme consigné | — |

## Next (ordre strict, pour Thomas/Claude côté Windows)

Ne pas inverser : **ponts d'abord, `.env.local` ensuite, relance en dernier.**
Poser les jetons avant d'allumer les ponts armerait des outils sans backend
(phrases « ne répond pas » à la voix au lieu d'une réponse directe).

1. **Windows PowerShell, 2 fenêtres** (depuis `D:\BGB Training\MOTHER-dev`) :
   `set CODEX_BRIDGE_TOKEN=<hex>` + `python -m native.codexbridge.bridge`
   (8765) ; `set CLI_BRIDGE_TOKEN=<hex>` + `python -m native.clibridge.bridge`
   (8766). Générer : `python -c "import secrets;print(secrets.token_hex(32))"`.
2. **Pont Muse (shell WSL normal, pas sandbox)** :
   `bash /mnt/e/AI/Hermes2/tools/muse_bridge_start.sh`
   => `:19124/health` 200 + `:4056/mcp` up.
3. **`.env.local`** (3 lignes, jamais commit) : les 2 jetons identiques
   aux ponts + `MUSE_BRIDGE_URL=http://host.docker.internal:19124`.
   Ne pas poser `CLI_BRIDGE_HERMES=1` (Hermes reste OFF à la voix).
4. **Relance ciblée** `dev/scripts/relancer_routeur.sh`, contrôler la ligne
   `OUTILS: ask_claude, ask_codex, ask_muse, web_search`, puis 1 tour PTT
   par outil (question fichiers => Codex, raisonnement => Muse, revue =>
   Claude, actu => web). En cas d'échec : les fallbacks parlables sont
   le comportement voulu, pas une panne.
5. **Hermes voix** : ne rien faire avant décision explicite (code + tests
   prêts : `register_ask_hermes` + `CLI_BRIDGE_HERMES=1` + binaire `hermes`
   sur le PATH Windows + levée de l'invariant).

## Ping OC

OUT coffre + copie repo : `nights/2026-09-15-MUSE-OUTILS-PONTS.md`.
Voix/TTS/live : non touchés. SAWB : non touché. Hermes2 : non touché
(lecture seule + 1 pont `/tmp` éphémère, arrêté).
