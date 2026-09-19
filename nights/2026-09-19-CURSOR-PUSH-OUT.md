---
date: 2026-09-19
heure: ~20:10 Europe/Paris
type: out
lane: CURSOR-PUSH
cible: OC (deadline 20:50) + Claude (WRAP-SOIR)
auteur: Cursor (Grok 4.6) — session desktop stop
deadline: 20:50 Europe/Paris
branche: nuit/2026-08-27
---

# CURSOR OUT — stop + push prêt — 19 sept 20:50

Thomas absent. Ordre : **stop, préparer le push, OUT `nights/` obligatoire**.
Cette session n'a **pas** codé de lane : reçu l'ordre d'arrêt.

`.env.local` **non touché** dans ce run. Aucune valeur de secret affichée.

## Git (commandes vues)

```
branche  * nuit/2026-08-27  [ahead 1 → origin]
HEAD     0570d46 Soir 19 sept : carte figee Granite+Whisper large-v3+Magpie Sofia, C1-C4 C8-C12, notes nights/
gitignore .env / .env.local / _tmp_*.py / .carte-secrete* / .carte-reel* / enregistrements/
check-ignore OK
git ls-tree HEAD | carte-secrete / .env.local / enregistrements → aucune ligne
```

Le commit principal **0570d46** était déjà sur la branche (165 fichiers, +11071/−263) au moment du stop. **Pas amendé** (auteur git = Thomas, pas ce run). Suite = restes encore sur disque (ce commit).

## Exclus (toujours)

| Chemin | Pourquoi |
|---|---|
| `.env` `.env.local` | secrets |
| `nights/**/.carte-secrete*.json` `.carte-reel*.json` | cartes aveugles |
| `nights/degustation-19/oreille/enregistrements/` | voix de Thomas |
| `logs/` `models/` `dev/scripts/_tmp_*.py` | déjà ignorés |

WAV TTS dégustation **dans** 0570d46 (~14 Mo). WAV oreille **hors** commit.

## Dans 0570d46 (à pousser)

C1 chargeur env · C2 sondes/bandeau · C3 module JeV · C4 web multi-fournisseurs · C5 `remote_tts` · C8 `src/i18n` · C9 Magpie+nombres · C10 PTT · C11 prompt · C12 `calculer` · P0-2 `carte_figee.env` + lanceurs · veille HF · banc oreille · notes `nights/2026-09-19-*` · captures C2 · `degustation-19/`.

## Suite (ce commit, restes après 0570d46)

| Fichier | Pourquoi |
|---|---|
| `nights/2026-09-19-CURSOR-PUSH-OUT.md` | cet OUT |
| `nights/2026-09-19-P0-2-CARTE-OUT.md` | OUT P0-2 arrivé après le 1er commit |
| `nights/2026-09-19-PUSH.md` | runbook OC avec hash |
| `native/presence/app.py` `.env.example` | restes C8 / commentaires MOUTH distant |
| `dev/tests/test_hostagent_env_local.py` | registre `{web_search, calculer}` |
| `dev/tests/test_jev_branchement.py` | tests `jev_ignore_tour` déjà dans serve |
| `src/mouth/remote_tts.py` | cosmétique log |

## Troués pour lundi

| Lane | État |
|---|---|
| **P0-1** copie SSD `E:` | pas d'OUT |
| **C1 live** | boot + tour outil **non** (feu vert relance jamais donné) |
| **C2 live pont** | HTTP `:1` prouvée ; pont `:8765` **non** tué ; voix alerte **non** |
| **C4 live** | SearXNG 0 résultat ; repli code présent |
| Bug 1er tour / C13 `pythonw` | encore ouvert |

## Ne pas casser

Stack live : `mother-core-dev`, llama `:8080` Granite, host-agent `:8001` via `/tmp/relance_hostagent.sh`, Magpie `:8092` CUDA. Pas de `docker compose up` / recreate.

## Push OC (une commande)

```powershell
cd "D:\BGB Training\MOTHER-dev"
git push origin HEAD
```

Coller l'URL dans `[[2026-09-19-PUSH]]` comme hier.

## Done cette session

| Attendu | Statut |
|---|---|
| Stop | oui |
| OUT `nights/` | ce fichier |
| Commit principal | déjà `0570d46` |
| Commit restes + OUT | oui (celui-ci) |
| Push origin | **non** — OC ci-dessus |
| Secrets | aucun `.env.local` / carte secrète / WAV oreille dans l'arbre git |
