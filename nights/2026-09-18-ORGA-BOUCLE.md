---
date: 2026-09-18
heure: ~20:21 Europe/Paris
type: orch
auteur: OC
objectif: boucler projet technique (idéal ce soir)
intervention_thomas: minimale
---

# ORGA 18 sept — boucle technique (anti-fiasco)

## Objectif soir
Fermer le **chantier technique** hyper-ambient pour la soutenance (25) / livrable dimanche:
harnais prouvable, voix claire, UI pas ridicule, SKU10 smoke, docs techniques, GitHub fin de lot.

## Rôles
| Qui | Rôle | Autonomie |
|---|---|---|
| **Thomas** | 1× « go » ; 1–2 PTT/visuels en fin de lot ; go push | Pas de micro-dispatch |
| **Claude** | **Lead technique** — découpe, assigne Cursor/Muse, décide how, WRAP+push | Session UNIQUE ; back/forth Thomas seulement si blocker dur |
| **Cursor** | Workhorse code (UI + fixes assignés) | 1–2 lanes max, fichiers disjoints |
| **Muse** | Harnais / onboarding LLM / ponts (cadrage→câble si Claude assigne) | Pas de fan-out libre |
| **Codex** | **Backup only** — remplace Cursor OU Claude OU Muse si grillé/timeout | Jamais 4e lane parallèle « pour avancer » |
| **OC** | Horloge, coffre, start/stop stack, briefs, mirroirs OUT, ping Claude si stuck >N min | Pas de how produit ; pas de kill/relaunch Claude en boucle |
| **OG** | Kanban / mémoire | Pas d'exec |

## Flux (Thomas n'intervient presque pas)
1. **OC** écrit ASSIGN soir + briefs (ce fichier) ; start stack une fois
2. **Claude** (1 session -c MOTHER-LEAD si déjà, sinon 1 new nommée **une fois**) lit ASSIGN ; produit PLAN-TECH-18 ; assigne Cursor + Muse via fichiers OUT
3. **Cursor** / **Muse** livrent OUTs réels dans nights/
4. **OC** clock: toutes les ~25–30 min check OUTs ; si Claude idle sans OUT → **1 nudge** fichier (pas 5 relaunch)
5. Smoke: OC prépare ; Thomas fait **1 créneau test** (~10 min) quand Claude dit READY
6. Fin: Claude WRAP + push GitHub ; **puis** OC unload si Thomas SAWB

## Lanes ce soir (Claude tranche l'ordre exact)
| Lane | Owner | Done quand |
|---|---|---|
| L1 Harnais | Muse (+ Cursor si code) | PTT→Codex prouvé OU doc blocker clair ; :8765 OK ; tool-loop pas de tempête |
| L2 Voix clarté | Claude decide → Cursor si besoin | Voix « précédente claire » rétablie ou A/B noté + choix lock |
| L3 UI Presence | Cursor | 1 geste HA **réel** (pas que transparent) + capture |
| L4 SKU10 + panne/reprise | Claude | Smoke SKU10 + script soutenance 1 page |
| L5 Docs + GitHub | Claude fin de lot | WRAP-18 + PLAN + push |

Codex = backup d'**une** lane en panne seulement.

## Règles anti-17-sept
- Pas de décharge stack avant WRAP Claude
- Pas de nouvelle session Claude à chaque nudge → **-c même nom**
- .ps1 → toujours .cmd / powershell -File
- OC ne fan-out pas Muse+WS+Cursor sans ASSIGN Claude
- Preuve = fichier / PONG / test — pas de statut
- Secrets jamais dans chat/commit

## Intervention Thomas (uniquement)
1. **Go** ce message (valide orga)
2. **Créneau test** quand ping « READY smoke » (~10 min)
3. **Go push** si Claude demande (ou standing « push fin de lot » dans ASSIGN)

Sinon OC+Claude+Cursor+Muse tournent seuls.

## Si flemme extrême
Mode réduit auto: L1+L2+L5 seulement ; L3 UI reporté ; L4 minimal papier.