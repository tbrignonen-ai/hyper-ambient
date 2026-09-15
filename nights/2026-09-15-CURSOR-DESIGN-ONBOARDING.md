---
date: 2026-09-15
type: out
auteur: Cursor (Grok exécutant)
cible: Thomas + OC + Claude
statut: livré localement — pas de push — pas de recreate
surface: native/presence uniquement
intent: "[[2026-09-13-INTENT-ONBOARDING-UX]]" (fichier absent du workspace ; repli Muse + Codex)
related:
  - "[[2026-09-14-MUSE-ONBOARDING-UX]]"
  - "[[2026-09-14-CODEX-ONBOARDING-DESIGN]]"
  - "[[2026-09-14-CODEX-ONBOARDING]]"
---

# Cursor — design app : éclair distant + onboarding Presence

Mission 15 sept : icône éclair qui s'allume pendant un appel distant, et **finir** le wizard Presence (PTT, raccourci, masquer config, a11y). Hors périmètre respecté : pas hostagent / TTS / brain / docker / session Claude. Pas de push. Pas de recreate.

## Verdict

Livrable UI visible, pas une refonte. Le wizard Codex (2 écrans) passe à **3 étapes skippables**. L'appel distant n'est plus seulement une bulle plus chaude : un **éclair dédié** s'allume, avec libellé et ligne d'état en texte.

## Éclair — appel distant

L'état `escalade` existe déjà côté transport (`type: state`). Presence ne fait que le **montrer**.

| État | Icône | Libellé | Ligne d'état |
|---|---|---|---|
| repos / écoute / réflexion / parole | éclair éteint (silhouette) | Modèle local | inchangée |
| **escalade** | éclair allumé + halo, pulsation | **Appel distant** | « Appel distant en cours — le modèle local interroge un modèle distant. » |

- Fenêtre app : badge à droite de la bulle, toujours visible (éteint/allumé). Couleur **et** texte, jamais la couleur seule.
- Overlay flottant : l'éclair n'apparaît **que** pendant l'escalade, pour ne pas charger l'orbe au repos.

Preuves visuelles :

- `nights/2026-09-15-cursor-onboarding-4-local.png` — éclair éteint, « Modèle local ».
- `nights/2026-09-15-cursor-onboarding-5-distant.png` — éclair allumé, « Appel distant », statut explicite.

## Onboarding — 3 étapes, tout skippable

`2026-09-13-INTENT-ONBOARDING-UX.md` n'était pas dans le dépôt (constat déjà fait par Codex le 14). Cadrage utilisé : Muse (PTT, raccourci, fenêtre qui se masque, a11y obligatoire) + design Codex (raccourci **dans l'application**, masquage = `iconify`, pas de faux hotkey global).

1. **Bienvenue** — trois réglages annoncés, aucun son enregistré, a11y en clair. Continuer / Passer.
2. **Appuyez pour parler** — `Espace` ou `Ctrl + Espace`, essai de maintien (souris / Entrée / Espace, **sans micro**), a11y. Continuer / Passer.
3. **Masquer la configuration** — promesse tenue : réduction barre des tâches, rappel par l'icône, croix/Échap ferment vraiment. Commencer / Commencer et masquer.

Après « Commencer » : raccourci affiché en permanence, bouton masquer, transcripts texte. `--onboarding` rejoue le parcours. Le raccourci choisi est bien poussé dans la session vocale (le lot du 14 gardait l'étiquette d'avant le wizard).

Hors lot, volontairement : vidéo optionnelle, raccourci Windows `RegisterHotKey`, tray, mode PTT bascule. Le libellé dit encore honnêtement « dans l'application ».

## Preuves exécutées

```
python -m pytest dev/tests/test_presence_onboarding.py -q
................                                                         [100%]
16 passed in 0.41s

python -m py_compile native/presence/app.py native/presence/onboarding.py native/presence/overlay.py
python native/presence/app.py --help
python native/presence/overlay.py --help
```

Captures wizard : `nights/2026-09-15-cursor-onboarding-1-bienvenue.png`, `-2-ptt.png`, `-3-masquage.png`.

Revue interactive :

```powershell
python native/presence/app.py --onboarding
```

## Fichiers

- `native/presence/onboarding.py` — copies, 3 étapes, persistance, logique éclair (sans Tk).
- `native/presence/app.py` — wizard, essai PTT, badge, statut distant, focus visible.
- `native/presence/overlay.py` — `dessiner_eclair`, éclair overlay seulement en escalade.
- `dev/tests/test_presence_onboarding.py` — 16 tests (dont wizard Tk + polygone allumé).

Aucun fichier hostagent / brain / TTS / docker modifié.
