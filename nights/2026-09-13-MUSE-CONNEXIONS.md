---
date: 2026-09-13
heure: ~18:40 Europe/Paris
type: out
auteur: Cursor (grok-4.6-xhigh)
cible: OC + Claude (lead)
statut: livré — CLI live verts, tour vocal sans outils
hermes: OFF
related:
  - "[[2026-09-13-BRIEF-MUSE-CONNEXIONS]]"
  - "[[2026-09-13-ASSIGN-CURSOR-CONNEXIONS]]"
  - "[[2026-09-13-CURSOR-PONTS-CLI]]"
  - "[[2026-09-11-SPRINT-1H]]"
---

# Connexions — Codex CLI / Claude CLI / web search (13 sept, soir)

Remplace le burn Muse (retry meta stream, SIGTERM, aucun OUT). Hermes non
allumé. Aucun commit. Aucun secret dans cette note.

Verdict en une ligne : **les trois CLI existent et répondent sur l'hôte ;
le produit ne les déclenche pas encore à la voix.**

## Tableau (démontrable vs racontable)

| Pont | Code | Tests (hôte, ce soir) | Processus / HTTP | Déclenché par la voix |
|---|---|---|---|---|
| **Codex CLI** | `tools_codex.py` + `native/codexbridge` | verts | CLI **PONG 8,6 s** ; pont **8765 down** | **Racontable** — jeton absent, pont éteint, host-agent pas lancé |
| **Claude CLI** | `tools_cli.py` + `native/clibridge` | verts | CLI **PONG 2,2 s** ; pont **8766 up, 401 sans jeton** | **Racontable** — pont live côté hôte, jeton **absent du conteneur** |
| **Web search** | `tools_web.py` (Tavily) | verts (mocks) | API **joignable, 401 sans clé** ; SearXNG local **30 hits** | **Racontable** — **jamais enregistré** dans `construire_registre` |
| **Hermes** | chemin écrit, verrou `CLI_BRIDGE_HERMES` | verts | **non invoqué** | **Éteint**, comme demandé |

## Comment le produit appelle (quand c'est câblé)

Chaîne unique, trois variantes :

```
voix → serve_hostagent.construire_registre
    → ToolRegistry + run_tool_loop + Gate(auto)
    → HTTP POST (client httpx injecté)
    → pont hôte (sauf Tavily, qui est l'API distante)
    → phrase parlable (jamais JSON / HTTP / traceback à l'oreille)
```

| Outil | Déclencheur | Cible | Argv / contrat |
|---|---|---|---|
| `ask_codex` | `CODEX_BRIDGE_TOKEN` + client HTTP | `CODEX_BRIDGE_URL` défaut `http://host.docker.internal:8765/ask` | pont → `codex exec --sandbox read-only --skip-git-repo-check --ephemeral -C <dépôt> -o <fichier>` |
| `ask_claude` | `CLI_BRIDGE_TOKEN` + client HTTP | `CLI_BRIDGE_URL` défaut `http://host.docker.internal:8766/ask` body `{question, agent: claude}` | pont → `claude -p --output-format text --restricted --permission-mode plan --permission-prompts none` |
| `ask_hermes` | **non enregistré** | même pont, `agent: hermes` | refusé tant que `CLI_BRIDGE_HERMES=1` n'arme pas **et** que le binaire n'est pas trouvable |
| `web_search` | **nulle part dans le registre live** | `https://api.tavily.com/search` Bearer `TAVILY_API_KEY` | `include_answer: true`, `search_depth: basic`, `max_results: 3` |
| `ask_muse` | `MUSE_BRIDGE_URL` | hors mission | second avis, pas un CLI hôte |

Annonces déjà écrites (`ANNONCES_OUTILS`) : Codex, Muse, Claude, **et**
`web_search` (« Je cherche ça sur le web. ») — orpheline : l'annonce existe,
l'outil n'est pas déclaré.

Registre **vide** si le jeton/clé manque : voulu, pour ne pas payer une boucle
d'outil qui ne peut dire que « je n'ai pas encore d'accès ». Conséquence ce
soir : même si `serve_hostagent.py` tournait, le tour resterait sans outil.

## Preuves live (appels courts, 13 sept ~18:35–18:40)

### 1. Codex CLI — démontrable

```
codex-cli 0.154.0
codex exec --skip-git-repo-check -s read-only --color never
  -C "D:\BGB Training\MOTHER-dev" -o <tmp> "Reponds exactement: PONG. Rien d autre."
EXIT=0  DUREE_S=8.6  modèle=gpt-6-astra  sandbox=read-only
OUT: PONG
```

Le workaround du 11 sept (`npx -y @openai/codex@0.154.0` parce que la 0.148
refusait `gpt-6-astra`) est **caduc** : la CLI globale est 0.154.0 et le modèle
de `~/.codex/config.toml` passe.

Pont produit : **rien n'écoute 8765** (`WinError 10061`, connexion refusée).

### 2. Claude Code CLI — démontrable

```
claude.exe  2.1.270 (Claude Code)
  -p --output-format text --restricted --permission-mode plan --permission-prompts none
  "Reply with the exact word PONG and nothing else."
EXIT=0  DUREE_S=2.2
OUT: PONG
```

(Premier essai via `Start-Process` a cassé le prompt sur les espaces PowerShell
→ Claude a cru le message vide. Relance `cmd /c` : PONG. L'argv du pont est
bon ; c'est le wrapping PowerShell qui avait menti.)

Pont produit **allumé** :

```
PID 21348  python -m native.clibridge.bridge
écoute 0.0.0.0:8766
POST http://127.0.0.1:8766/ask  sans Bearer / Bearer dummy
  → 401  {"ok": false, "error": "non autorise"}
```

Le pont n'accepte un body que s'il a un jeton (sinon `main()` fait
`SystemExit`) : **il tourne ⇒ un `CLI_BRIDGE_TOKEN` existe dans l'environnement
de ce processus hôte**. Il n'est **pas** dans `.env.local` ni dans le
conteneur — le produit ne peut pas l'utiliser.

Depuis `mother-core-dev` : `host.docker.internal` résout (IPv6 Docker Desktop),
`POST http://host.docker.internal:8766/ask` → **HTTP 401**. Le câble réseau
conteneur → pont Claude est **démontrable**. Il manque le Bearer.

### 3. Web search — démontrable hors produit, racontable dedans

**Tavily (chemin produit), sans clé, 13 sept :**

```
POST https://api.tavily.com/search
  {"query":"ping","include_answer":true,"max_results":1,"search_depth":"basic"}
→ HTTP 401  {"detail":{"error":"Unauthorized: missing or invalid API key."}}
```

Docs lues le même jour : <https://docs.tavily.com/documentation/api-reference/endpoint/search>
— `Authorization: Bearer <tvly-…>`, `include_answer` toujours supporté
(`true` / `basic` / `advanced`). Le code de `tools_web.py` est encore aligné.
Pas d'appel Tavily **crédité** : `TAVILY_API_KEY` absent de `.env.local` et du
conteneur.

**SearXNG local (preuve recherche, pas le produit) :** instance `searxng` Up,
`127.0.0.1:8080`. `!gh openai/codex` → **30 résultats**, `unresponsive=none`,
1er hit <https://github.com/openai/codex>. Bang `!go` → **0 résultat**
(généraliste muet ; pas une absence du web). SearXNG **n'est pas** branché
dans le harnais MOTHER.

## État machine (mesuré, pas raconté)

| Élément | Mesure ~18:35 |
|---|---|
| `mother-core-dev` | Up ; `Cmd=["/bin/bash"]` ; **un seul process : bash**. Pas de `serve_hostagent.py`. **8001 n'écoute pas.** |
| `docker-compose.yml` | `env_file: .env.local` ; `command: /bin/bash` ; **pas** d'`extra_hosts` (Docker Desktop fournit quand même `host.docker.internal`) |
| `.env.local` | existe (3 008 o). Clés ponts / Tavily / Muse : **absentes**. `.env.example` non plus. |
| Conteneur | `CODEX_BRIDGE_TOKEN`, `CLI_BRIDGE_TOKEN`, `TAVILY_API_KEY`, `MUSE_BRIDGE_URL`, `CLI_BRIDGE_HERMES` = **absent** |
| Tests hôte | `106 passed, 12 failed` sur les fichiers ponts + `test_outils_voix`. Les 12 échecs = `@pytest.mark.asyncio` **sans plugin chargé** sur ce Python 3.13 hôte (`async def functions are not natively supported`). `pytest-asyncio==0.21.1` est dans `requirements.txt` (image conteneur). **Pas une régression des ponts.** Ponts seuls : `test_clibridge` / `test_tools_cli` / `test_codex_bridge` / `test_tools_codex` / `test_tools_web` / `test_tavily_mock_only` **verts**. |

## Trous + patchs proposés (fichiers)

Rien n'a été patché ce soir : la consigne était de **livrer la note** avec
preuves. Ordre pour passer de racontable à démontrable à l'oreille :

1. **`.env.example` + `.env.local` (Thomas)** — placeholders vides, jamais de
   secret coffré ici :
   `CODEX_BRIDGE_TOKEN`, `CLI_BRIDGE_TOKEN`, `TAVILY_API_KEY`,
   `MUSE_BRIDGE_URL` (optionnel), `GATE_MODE`. Recréer / `docker start` le
   conteneur après remplissage (`env_file` n'est lu qu'au create).
2. **`dev/scripts/serve_hostagent.py` — `construire_registre`** — brancher
   `register_web_search` si `TAVILY_API_KEY` et `client` (même garde que
   Codex/Claude). Aujourd'hui l'import n'existe pas ; l'annonce `web_search`
   est morte. Corriger aussi le log
   `OUTILS: aucun (CODEX_BRIDGE_TOKEN absent)` : il ment si seul le jeton
   Claude manque.
3. **`dev/tests/test_outils_voix.py`** — un test
   `TAVILY_API_KEY` ⇒ `web_search` dans le registre, `danger="read"` ; un test
   sans clé ⇒ pas de `web_search`. Empêche la régression orpheline.
4. **Hôte, pas du code** — lancer `python -m native.codexbridge.bridge` (8765),
   le même geste que le clibridge déjà vivant. Puis **démarrer**
   `python3 dev/scripts/serve_hostagent.py` dans le conteneur (aujourd'hui
   bash idle). Vérifier la ligne `OUTILS: ask_claude, ask_codex, web_search`.
5. **Optionnel, plus tard** — backend SearXNG dans `src/brain/tools_web.py`
   (`http://host.docker.internal:8080/search?format=json`) quand Tavily n'a
   pas de clé. Utile (instance déjà Up, 0 quota) mais **contrat différent** :
   pas de champ `answer` parlable, il faudrait coller `title`+snippet comme
   Tavily le fait déjà en repli. Ne pas le faire avant d'avoir un Tavily
   live si Thomas veut le chemin d'origine.
6. **Ne pas faire** — `CLI_BRIDGE_HERMES=1` ; enregistrer `ask_hermes` ;
   `compose recreate` sans besoin ; commit.

## Ce qui débloque vraiment (ordre)

Le code des trois ponts est posé. Le trou n'est plus « écrire un client » :

1. Jetons / clé dans `.env.local` (décision Thomas).
2. Pont Codex allumé (Claude l'est déjà).
3. Host-agent lancé dans le conteneur.
4. Une ligne `register_web_search` (le seul trou **code** restant).

Sans (1)+(3), aucun outil ne s'entend. Sans (2), `ask_codex` tombe sur
« Codex ne répond pas pour l'instant, je continue sans lui. » Sans (4),
« cherche sur le web » n'existe pas pour le modèle.

## Ping OC

OUT coffre + copie repo : `nights/2026-09-13-MUSE-CONNEXIONS.md`.
Hermes OFF. Muse connexions : cette note **remplace** le burn.
VRAM / voix : non touchées. Rien à arrêter de mon côté (clibridge 8766
préexistant, laissé tel quel).
