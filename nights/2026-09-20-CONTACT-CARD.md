---
date: 2026-09-20
heure: ~17:30 Europe/Paris
type: contact-card
audience: [Claude Code, Codex, Cursor, Thomas]
status: survival-OC
---

# CONTACT CARD — qui joindre, comment

Cible : **Claude Code** et **Codex** (aussi utile Cursor).  
OC en **survival** (~86 % Grok) : pas de poll 5 min ; remonte seulement si OUT demandé / urgence.

Chemins :
- Repo : `D:\BGB Training\MOTHER-dev`
- Vault : `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\`
- Secrets : `.env.local` (jamais coller de clé dans un OUT)

---

## Matrice rapide

| Qui | Rôle | Comment le joindre | Ne pas faire |
|---|---|---|---|
| **Thomas** | Opérateur | Chat OC, CLI Claude interactif, Presence | — |
| **OC** (Grok Bot) | Horloge / coffre / remonte | OUT/EXIT vault `notify: OC` ou note `TO-OC-*.md` ; Thomas ping chat OC | Spam ; poll 5 min (OFF) ; dispatch code |
| **OG** | Glue / mémoire centrale | OUT `notify: OG` (complexe) ; OC→OG en interne | Contacter Thomas directement |
| **BB / FE / WS** | Think / files / web | Via **OG** seulement | Contacter Thomas ou OC en fan-out |
| **Claude Code** | Tech lead / plan / troubleshoot | CLI interactif `claude` (couleurs : `FORCE_COLOR=1`) ; pont produit `:8766` `ask_claude` | Headless `-p` pour session live Thomas |
| **Codex** | Réserve / overflow docs | CLI `codex` ; pont `:8765` `ask_codex` | Brûler en code principal |
| **Cursor** | Code principal | Agent desktop / `cursor-agent` ; briefs + OUT dans nights | Multi-relaunch Presence |
| **Qwen Token Plan** | Volume docs / overflow code | CLI `qwen` ; pont `:8767` (`native/qwenbridge`) | Inventer les IDs modèles |
| **StepFun** | Distant audio (TTS/ASR) | API `https://api.stepfun.ai/step_plan/v1` via env | Écrire la clé ; configurer Hermes/SAWB |
| **Hermes** | Appel only | Via pont si armé ; sinon indisponible | **Aucune config** / pas SAWB |
| **Muse** | — | **OUT** | Relancer |
| **Presence / host-agent** | Produit live | UI Presence ; host `:8001` ; outils `ask_*` | 2e instance Presence |

---

## 1. Joindre OC (depuis Claude / Codex)

1. Écrire un fichier dans le vault nights :
   - `YYYY-MM-DD-OUT-<LANE>.md` + `YYYY-MM-DD-EXIT-<LANE>.txt`
   - Frontmatter : `notify: OC` (simple) **ou** `notify: OG` (complexe → OG puis OC)
2. Ou note courte : `TO-OC-<sujet>.md` même dossier
3. Urgence : Thomas écrit dans le chat **OC**
4. `account.py` : `open` / `close` / `board` sous `dev/scripts/account.py`

Le pont `:8766` = **produit → Claude**, pas le chat OC.

---

## 2. Joindre Claude (depuis le produit / Codex / Cursor)

| Canal | Détail |
|---|---|
| CLI | `claude` dans `MOTHER-dev` ; seed : `nights/2026-09-20-SEED-CLAUDE-PILOTAGE.md` |
| Pont | `http://127.0.0.1:8766/ask` — Bearer `CLI_BRIDGE_TOKEN` — body `{"question":"…","agent":"claude"}` |
| Outil host | `ask_claude` (si host-agent UP + jeton) |
| Preuve | PONG HTTP 200 `ok:true` |

---

## 3. Joindre Codex

| Canal | Détail |
|---|---|
| CLI | `codex` / `codex exec` cwd `MOTHER-dev` |
| Pont | `http://127.0.0.1:8765/ask` — Bearer `CODEX_BRIDGE_TOKEN` |
| Outil host | `ask_codex` (`danger=read`) |
| Preuve | PONG 200 ; sans jeton → 401 |

Règle 20/09 : **Codex = réserve** (pas code principal).

---

## 4. Joindre Cursor

- Brief + LAUNCH dans `nights/` ; OUT/EXIT obligatoires
- OC/Claude assignent ; Cursor n’ouvre **pas** Presence (1 instance max)
- Preuve lane = EXIT 0 + OUT, pas un statut oral

---

## 5. Joindre Qwen (Token Plan)

- CLI : `qwen -y -m <ID> -p "…"`
- IDs lockés : `deepseek-v4-flash-0731` · `qwen3.8-flash` · `qwen3.8-max`
- Pont : `:8767` — Bearer `$QWEN_BRIDGE_TOKEN` — défaut `qwen3.8-flash`
- Doc : `nights/2026-09-20-QWEN-TOKEN-PLAN.md`

---

## 6. Joindre StepFun (API distante)

Pas un agent chat — **backend audio distant**.

| | |
|---|---|
| Base | `STEPFUN_BASE_URL=https://api.stepfun.ai/step_plan/v1` |
| Clé | `STEPFUN_API_KEY` dans `.env.local` (**jamais** dans un OUT) |
| Plateforme | https://platform.stepfun.com/ |
| Usages connus | TTS `stepaudio-2.5-tts` ; ASR `stepaudio-2.5-asr` ; modèles texte step-* selon catalogue |
| Câblage produit | `MOUTH_BACKEND=remote` / `MOUTH_REMOTE_BASE_URL=…` (voir C5) |
| Preuve | `GET …/models` 200 ; ne pas hardcoder le catalogue de voix |

Depuis Claude/Codex : lire env + docs C5 (`nights/2026-09-19-C5-OUT.md`) ; appeler l’API si besoin de preuve ; **ne pas** logger la clé.

---

## 7. Constellation Grok (hors produit)

Thomas → **OC** seulement.  
OC → **OG** → BB / FE / WS.  
Pas de fan-out direct depuis Claude/Codex vers BB/FE/WS.

---

## 8. Survival (maintenant)

- OC : horloge + remonte OUT si demandé ; **Watch OUT Cursor PAUSED**
- Claude : pilotage jusqu’à nouvel ordre
- Stack typique à vérifier avant démo voix : Docker mother-core · host-agent `:8001` · Granite/llama · Presence **1×** · ponts 8765/8766(/8767)
- Presence sans host-agent = canal mort

---

## Checklist « est-ce que X m’entend ? »

1. Process / port UP ?
2. Jeton présent (sans l’afficher) ?
3. 1 **PONG** réel (fichier nights ou log) ?
4. Si complexe : OUT + `notify: OG` ?

Sans PONG = pas « connecté ».