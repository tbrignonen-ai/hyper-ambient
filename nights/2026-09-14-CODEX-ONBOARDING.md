---
date: 2026-09-14
type: out
statut: livré localement — pas de push
---

# OUT — onboarding Codex

## Livré

- Design produit et technique : `nights/2026-09-14-CODEX-ONBOARDING-DESIGN.md`.
- Wizard première ouverture en deux écrans dans `native/presence/app.py` : Bienvenue, puis PTT/raccourci.
- Configuration persistante et validée dans `native/presence/onboarding.py`.
- Choix `Espace` / `Ctrl + Espace`, avec libellé volontairement limité à l'application.
- PTT au maintien par souris, raccourci choisi, ou Entrée lorsque le bouton est focalisé.
- Parcours Tab, focus PTT visible, labels textuels et transcriptions conservées.
- Bouton « Masquer la configuration » : réduction dans la barre des tâches, donc rappel natif par son icône.
- Option `--onboarding` pour rejouer le wizard sans supprimer la préférence.
- Quatre tests unitaires ciblés dans `dev/tests/test_presence_onboarding.py`.

## Vérifications

- Compilation Python de `app.py`, `onboarding.py` et `overlay.py` : OK.
- Chargement de la CLI et `--help` sans dépendances audio : OK (import audio désormais paresseux).
- Écriture, relecture, normalisation et traduction Tk des préférences : OK via assertions locales.
- La commande pytest n'a pas pu être lancée dans le Python uv nu : `pytest` n'y est pas installé.
- Le lancement graphique interactif n'a pas été forcé. Dans ce Python uv nu, `numpy` manque : l'UI peut s'ouvrir, puis signale la dépendance audio absente en texte après l'onboarding. Aucun paquet n'a été installé dans ce sprint.

Commande de revue sur un environnement hôte déjà équipé :

```powershell
python native/presence/app.py --onboarding
```

## Décisions et limites

- La vidéo reste optionnelle dans le design et non implémentée dans ce lot minimal.
- Pas de faux raccourci global : Tkinter ne capte le choix que lorsque l'app a le focus. Une future couche `RegisterHotKey` pourra tenir cette promesse au niveau Windows.
- Les deux briefs demandés, `2026-09-13-INTENT-ONBOARDING-UX.md` et `2026-09-14-SPRINT-ONBOARDING-30.md`, étaient absents des deux workspaces au moment du travail. Le cadrage explicite de la demande et `2026-09-14-MUSE-ONBOARDING-UX.md` ont servi de référence.
- Aucun push, Docker, Hermes, image ou sample voix.
