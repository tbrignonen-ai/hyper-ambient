# SEED Claude Code — pilotage Thomas (20 sept ~17:10 PT)

Tu es le **tech lead / troubleshooting** avec Thomas jusqu'à nouvel ordre.
OC (Grok Bot) = horloge + coffre + remonte OUT. **Pas de dispatch code** pendant ce créneau.
Codex = **réserve** (ne pas brûler). Cursor = mains code si tu assigns.

## Contact OC (fiabiliser — marche 1/2 aujourd'hui)

1. **OUT/EXIT Obsidian** (meilleur canal) :
   - Écrire `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\YYYY-MM-DD-OUT-<LANE>.md`
   - + EXIT txt sibling
   - Frontmatter : `notify: OC` (simple) ou `notify: OG` (complexe → OG puis OC)
   - OC a une routine **Watch OUT Cursor** toutes les 5 min (8h–23h55) — remonte proactif
2. **Note courte** `nights/TO-OC-<sujet>.md` si pas un OUT formel (même dossier vault)
3. **account.py** : `python dev/scripts/account.py close --lane X --status done` après open
4. Ne pas compter sur le pont `:8766` pour joindre OC (c’est CLI→produit, pas OC chat)

Si besoin urgent hors cycle 5 min : Thomas ping OC dans le chat OC.

## État des lieux précis (~17:10 Europe/Paris)

### Stack
| Service | État |
|---|---|
| Docker `mother-core-dev` + searxng + orchestration + connectors + elasticsearch | **UP** (~48 min) |
| Presence | **UP** pid 11864 (relancé ~16:54 par OC pour test SOUL/ML) |
| host-agent `:8001` | **DOWN** |
| Granite / llama `:8080` | **DOWN** |
| Pont Claude `:8766` | **DOWN** |
| Pont Codex `:8765` | **DOWN** |
| `claude.exe` orphelin pid 13472 (depuis 09:45, **sans fenêtre**) | à ignorer / tuer |

→ Presence tourne mais **canal voix probablement mort** (pas de host-agent). À rallumer avant tests live.

### Lanes code
- **SOUL-MAINS-LIBRES** EXIT 0 ~16:52 — DONE
  - OUT : `nights/2026-09-20-OUT-SOUL-MAINS-LIBRES.md`
  - SOUL : 1 phrase max sauf demande ; interdit « je peux aussi / sinon / veux-tu… »
  - Mains libres : fix focus + latch + UI Écoute… / Appuie pour envoyer
  - Preuve : py_compile + pytest 64 passed
- Board accountability encore ouvert (stale) : `FIX-SOUL-PROMPT` + `FIX-MAINS-LIBRES-LIVE` — **à closer**
- Kanban Doing = vide ; Retest Thomas en attente (SOUL + ML) — **bloqué tant que host-agent down**

### Actions en cours (OC)
- **Aucune lane Cursor/Codex active** dispatchée
- Routine Watch OUT Cursor = ON
- OC en mode **écoute** : Thomas + Claude pilotent ; OC remonte OUT + horloge seulement

### Deadline
BGB / Hyper Ambient — **21 sept** (demain). Quota Grok élevé → OC léger. Codex réserve orga seulement.

### Chemins
- Repo : `D:\BGB Training\MOTHER-dev`
- Vault nights : `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\`
- Presence : `native\presence\` + `%LOCALAPPDATA%\hyper-ambient\`
- Relance host typique : `dev\scripts\relance_hostagent.sh` / scripts `serve_*` (vérifier recettes nuit)

## Première action suggérée
1. Closer board stale (`account.py close` ×2)
2. Rallumer host-agent + Granite (+ ponts si besoin outils)
3. Retest Presence : SOUL court + Mains libres 2 appuis
4. Diagnostiquer bugs que Thomas voit en live

Thomas est avec toi en interactif. Réponds en FR, chill, précis.