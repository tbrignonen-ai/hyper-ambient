---
date: 2026-09-19
type: protocole-test
auteur: Claude (lead technique) — conduit avec Thomas (juge)
usage: dossier BGB §4 (plan de tests) — méthode de sélection des modèles locaux
---

# Protocole de dégustation des modèles locaux

## Principe
Sélection des modèles embarqués (voix, oreille, cerveau) par **tests à l'aveugle jugés par l'utilisateur final**,
complétés par des **mesures objectives** relevées automatiquement. Candidats issus d'une **veille par l'API Hugging Face**
(`dev/scripts/veille_hf.py`), pas d'une recherche web ; chaque candidat vérifié sur sa fiche officielle.

## Contraintes éliminatoires
Français · tient avec oreille + voix dans **10 Go de VRAM au total** · exécutable nativement sous Windows (GGUF / ONNX / CTranslate2) · licence compatible.

## Voix (fait le 19/09)
Même phrase piège (R, nasales, « u ») pour chaque candidate, **volume égalisé** (RMS −20 dBFS) pour ne pas favoriser la plus forte,
fichiers renommés A–D au hasard (graine fixe), correspondance cachée révélée **après** le verdict.
Résultat : Supertonic F5 ×0,88 (locale) préférée à l'aveugle devant F3 et deux voix distantes StepAudio. Banc n°2 (nouveautés HF) en cours.

## Oreille
5 phrases réelles enregistrées par l'utilisateur (micro réel, conditions réelles) → transcrites par chaque candidat ;
mesures : exactitude (taux d'erreur de mots vs texte de référence), temps de calcul, VRAM max ; transcriptions anonymisées O1…O6.

## Cerveau — dégustation semi-improvisée
Pour chaque cerveau (lettre, nom caché), 7 thèmes imposés ; **l'utilisateur improvise sa propre question** dans chaque thème
(évite qu'un modèle soit bon sur un script appris) et parle à MOTHER à la voix, dans l'application réelle.
| Thème | Ce qu'on juge |
|---|---|
| 1. Conversation / personnalité | naturel, chaleur, français parlé |
| 2. Culture générale | exactitude, aveu d'ignorance |
| 3. Consigne de forme (« en une phrase », « détaille ») | respect de la longueur demandée |
| 4. Besoin d'info à jour | déclenche la recherche web au lieu d'inventer |
| 5. Suite de conversation (« et lui ? », « ça ») | tient le contexte |
| 6. Raisonnement concret (horaires, calcul) | justesse |
| 7. Question d'onboarding simple | clarté pour un débutant |
Note 1–5 par thème + commentaire, saisis dans une fenêtre dédiée ; mesures auto : délai avant premier mot, vitesse, VRAM.
