---
date: 2026-09-13
time: "~17:40 Europe/Paris"
type: handover
recipient: Claude
status: current
---

# Handover — Claude reprend le lead technique

## Cadre immédiat

- Crazy Dev Day du **13 septembre 2026**, wrap prévu vers **18h**.
- Soutenance le **25 septembre 2026**.
- Ce document fige la relève technique à environ **17:40, Europe/Paris**.
- Ne pas coder sur la base de suppositions qui contredisent cet état.

## Routage des rôles

| Rôle | Responsable |
|---|---|
| Lead technique | **Claude** |
| Code / exécution | **Cursor** |
| Cerveau | **Codex** |
| Horloge / dispatch | **OC** |
| High-level | **Muse** |

## Décisions verrouillées

- **World model : DROPPED.** Il ne fait plus partie de la trajectoire.
- **Onboarding UX : intention verrouillée.**
- **Budget VRAM : environ 8 à 10 Go.**

## Stack voix et ASR — état exact

### Option 2, jour 1

La stack du jour 1 était :

- MiniCPM5-2B ;
- Qwen3-ASR-0.6B ;
- Piper.

Le problème ASR float/Half est **FIXÉ** grâce à un hook sur `audio_tower`.

Les voix Piper `siwis`, `upmc` et `tom` ont été écoutées cet après-midi et jugées mauvaises par Thomas. Elles ne constituent pas la voix actuelle retenue.

### TTS actuellement LIVE

- Moteur : **Pocket TTS `french_24l`**.
- Voix : **`estelle`**.
- Profil : **`aurora`**.
- Service : hostagent avec un PID récent.
- Exécution : **CPU, 0 VRAM**.
- Repère historique : c’est déjà la voix que Thomas avait retenue le **6 septembre**.

## Action en cours confiée à Cursor

Thomas veut **10 samples MP3 français longs**, provenant de **modèles TTS différents**. La cible esthétique est la voix « **Aura Ray** » sur YouTube.

**Cursor s’en charge.** Claude garde le lead technique et arbitre à partir des résultats ; Codex ne code pas le produit dans cette relève.

## Point de reprise pour Claude

Prendre ce document, le bloc de tête de [[../REPRENDRE-ICI|REPRENDRE-ICI]] et celui de [[../NEXT|NEXT]] comme état courant. Les notes antérieures servent de contexte historique ; en cas de contradiction, les décisions ci-dessus prévalent.
