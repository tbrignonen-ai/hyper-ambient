---
date: 2026-09-17
type: out
auteur: Cursor (Grok exécutant)
cible: Thomas + OC + Claude
statut: livré localement — pas de push
surface: native/presence uniquement
related:
  - "[[2026-09-17-BRIEF-CURSOR-UI]]"
  - "[[2026-09-15-CURSOR-DESIGN-ONBOARDING]]"
---

# Cursor — UI Hyper Ambient 17 sept

Mission : vraie présence HA (transparence + formes / motion), suite onboarding FR, **sans casser** l’éclair distant ni le wizard 3 étapes. Hors périmètre respecté : pas brain / TTS / host-agent / docker. Pas de push.

## Fait

La fenêtre app n’est plus un panneau opaque. Le bureau **perce** via `transparentcolor` (`#010203`, même clé que l’overlay). Une **nappe** (blobs lents + rubans) se dessine derrière. L’orbe n’est plus trois ovales : blobs irréguliers, halos décalés, filaments toujours en mouvement (même au repos), grains en orbite.

Wizard **toujours 3 étapes skippables**, libellés **FR only**. Chaque étape montre l’orbe vivant. Vitre sombre pour le texte (lisible) ; le fond autour reste percé.

Éclair 15 sept **intact** : éteint = « Modèle local » ; allumé seulement en `escalade` = « Appel distant » + statut en clair.

## Chemins

- `native/presence/overlay.py` — `points_blob`, `dessiner_nappe`, `dessiner_orbe` ; overlay démo/live réutilise le même dessin.
- `native/presence/app.py` — fenêtre percée, nappe, orbe partagé, vitres, wizard animé.
- `native/presence/onboarding.py` — phrase d’accueil (« La lumière bouge avec elle. ») ; 3 étapes inchangées.
- `dev/tests/test_presence_onboarding.py` — orbe/nappe + lock FR + transparence.

Aucun fichier hostagent / brain / TTS / docker modifié.

## Captures

Coffre + repo `nights/` :

| Fichier | Quoi |
|---|---|
| `2026-09-17-cursor-ui-1-bienvenue.png` | Étape 1/3, orbe, Continuer / Passer |
| `2026-09-17-cursor-ui-2-ptt.png` | Étape 2/3, Espace / Ctrl + Espace, essai |
| `2026-09-17-cursor-ui-3-masquage.png` | Étape 3/3, Commencer / Commencer et masquer |
| `2026-09-17-cursor-ui-4-local.png` | App : orbe flottant, éclair éteint « Modèle local » |
| `2026-09-17-cursor-ui-5-distant.png` | Escalade : orbe braise, éclair allumé, statut distant |
| `2026-09-17-cursor-ui-6-overlay-parole.png` | Overlay percé, parole |
| `2026-09-17-cursor-ui-7-overlay-escalade.png` | Overlay + éclair pendant l’escalade |

Script de prise : `nights/_capture_ui_ha_2026-09-17.py` (session vocale volontairement non lancée).

## Tests

```
python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_interruption.py -q
....................                                                         [100%]
20 passed in 0.85s
```

(16 onboarding de base + 2 dessin HA/FR + 2 interruption.)

```
python -m py_compile native/presence/app.py native/presence/overlay.py native/presence/onboarding.py
```

Revue visuelle :

```powershell
python native/presence/app.py --onboarding
python native/presence/overlay.py --demo
```

## Next

- Relire live sur le bureau réel (Luciole + Presence) : nappe vs fond clair / sombre.
- Option post-soutenance : coins de vitre arrondis (Tk ne le fait pas nativement), raccourci Windows global (hors ce lot).
- EN + images périodiques = **après** soutenance, comme le plan soir.
