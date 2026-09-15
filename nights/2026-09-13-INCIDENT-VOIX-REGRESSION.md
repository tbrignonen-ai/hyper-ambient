---
date: 2026-09-13
type: assign
heure: ~17:05
---
# INCIDENT — régression voix (Thomas)

## Feedback Thomas (littéral, à prendre au sérieux)
- « grosse regression au niveau de la voix, c etait mieux avant qu on commence la session »
- « Les reponses doivent etre analysees, la c etait pourri »
- « la voix entrecoupee »
- « etre bete » (garder simple)
- Veut **Codex ET Cursor** dessus.

## Etat
- Avant session / 8 sept validé : Piper `fr_FR-siwis-medium` + profil `aurora`
- Aujourd hui on a switché upmc+mother puis Thomas dit entrecoupé / pourri
- OC a **immédiatement** forcé un revert runtime siwis+aurora via `MOUTH_VOICE_FORCE` / `MOUTH_PROFILE_FORCE` + relancer_routeur — Cursor doit **figer** ce revert dans `.env.local` + `relancer_routeur.sh` si ce n est pas déjà le cas, puis diagnostiquer l entrecoupe
- Hyper-ambient ouvert côté Thomas

## Roles
- **Codex = cerveau** : diagnostiquer POURQUOI entrecoupé + réponses pourries (buffer audio, profil mother reverb/doublage, upsample, WS frames, filler, TTFT, brain model). Lire logs, code mouth/transport, pas coder le fix principal.
- **Cursor = code** : appliquer les fixes (audio continu, config voix). Figer siwis+aurora tant que Thomas n a pas choisi autre chose.
