---
date: 2026-09-20
heure: ~15:46 Europe/Paris
type: urgence
auteur: OG
correction: Thomas — Codex = backup OC/orga, pas code préemptif
---

# Urgence quota Grok Bot + backup Codex

## Constat
- Grok Bot / OC **~77 %** usage ; reset **~4 jours**
- Rendu BGB demain → quota tendu

## Règle LOCKED (Thomas 15:46)
| Rôle | Qui |
|---|---|
| **Codex** | **Backup de OC / orga** si Grok saturé — **PAS** à charger maintenant pour le code |
| Code (patches Presence, etc.) | **Cursor** (chat actif) — ou rien si pas Cursor |
| Horloge / ponts / digests légers | **OC** |
| Kanban / mémoire | **OG** |
| Lead / Thomas | **Claude** |
| Volume docs | **Qwen** flash |
| Muse | **OUT** |

## Interdit
- Burn préemptif Codex « au cas où »
- Relancer Codex FIX-STOP (OC a stoppé — **ne pas relancer**)

## Si OC/Grok saturé (alors seulement)
1. Codex peut reprendre **orga légère** (clock/notes), pas forcément le code
2. Code : Cursor desktop déjà chaud, ou pause lane
3. OG = kanban only

## Lane critique
`FIX-STOP-MAINS-LIBRES` → **Cursor only** (`e3e3ba67…`). Stop + mains libres sans PTT. INTERDIT relaunch Presence.