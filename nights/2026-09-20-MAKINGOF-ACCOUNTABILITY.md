---
date: 2026-09-20
heure: ~10:27 Europe/Paris
type: making-of
lane: ACCOUNTABILITY
auteur: OC (demande Thomas)
---

# Making-of — accountability (circuit ferme)

## Decision Thomas (J-1)
Avant un prompt d'orga complexe : l'accountability n'etait pas assez forte (on voyait rarement la **fin** reelle des taches). Il a ajoute une lane et demande un mini-outil **sans perte d'eau**.

## Regle de notification (clarifiee)
| Complexite | Qui gere | Qui est informe a la fin |
|---|---|---|
| **simple** | **OC seul + ponts** (Cursor / Codex / Qwen / Claude), comme hier | pas besoin d'OG |
| **complexe** | flotte / orga | **OG** d'abord ; **OG informe OC** |

## Outil
- `dev/scripts/account.py` — open / pulse / close / scan / board / status
- `nights/ACCOUNTABILITY-LEDGER.jsonl`
- `nights/ACCOUNTABILITY-BOARD.md`
- Sur `close`/`scan` d'une lane `complex` : hint `NOTIFY=OG` → OC envoie a OG

## Dossier
Section making-of / orchestration de l'annexe technique.