---
date: 2026-09-14
type: muse-ux
intent: "[[2026-09-13-INTENT-ONBOARDING-UX]]"
sprint: "[[2026-09-14-SPRINT-ONBOARDING-30]]"
statut: proposition UX — pas de code, pas de spec technique
---

# Onboarding UX — hyper-ambient (proposition Muse)

Principe : le modèle local se charge, puis **c'est lui qui guide l'onboarding à la voix**. L'écran sert à peine : il configure, puis **se masque**. La vidéo / présence visuelle est **optionnelle** et reste après.

Règle d'ambiance : une chose à la fois, phrases courtes, jamais de formulaire bloquant. Tout est faisable à la voix seule. Tout est skippable.

---

## Parcours en 6 étapes (~2 min, tout skippable)

### 1. Accueil — « Je me charge, reste avec moi »
- Copy : « Je me réveille. Ça prend quelques secondes. »
- Ambiance : halo calme + progression douce, pas de % anxiogène.
- Sortie : passe seul à l'étape 2 quand le modèle est prêt. Bouton « Passer » discret.

### 2. Bonjour du modèle — « C'est lui qui parle »
- Copy (voix + sous-titre) : « Salut, c'est moi. Je vais t'aider à régler ça en une minute. »
- Effet : l'utilisateur comprend immédiatement que **le modèle local parle**.
- Choix : [Continuer] / [Lire seulement, sans voix].

### 3. Voix — « Appuie pour parler »
- Copy : « Pour me parler, maintiens appuyé. Essaie : dis bonjour. »
- PTT : un gros bouton press-to-talk, + **raccourci clavier à choisir** (défaut proposé, modifiable en un geste).
- Feedback : l'appui s'illumine, la voix confirme « Je t'entends bien. »
- A11y : tout le PTT est aussi faisable au clavier (focus visible, activation Entrée/Espace maintenu ou bascule), et en texte seul si micro refusé/indisponible.

### 4. Fenêtre config — « Elle va disparaître »
- Copy : « Je règle deux bricoles. Après, cette fenêtre se cache toute seule. »
- Contenu max : micro + voix de réponse + raccourci PTT. Rien d'autre.
- Promesse tenue : à la fin de l'étape 5, la fenêtre **se masque** (pas fermée, rappelable d'un geste).

### 5. Vidéo optionnelle — « Tu veux me voir ? »
- Copy : « Tu veux une petite présence visuelle, ou juste ma voix ? »
- Choix : [Avec vidéo] / [Voix seule]. Défaut : voix seule.
- Si vidéo : elle apparaît doucement et **reste** après l'onboarding. Coupable en un geste, sans retour config.

### 6. Premier moment — « On y est »
- Copy (voix) : « C'est prêt. La fenêtre se cache. Dis mon nom quand tu as besoin de moi. »
- La fenêtre config se masque. Reste : voix (+ vidéo si choisie).
- Rappel discret (10 s) : comment rappeler la config + rappel du raccourci PTT.

---

## PTT + raccourci + a11y (règles produit)

- **PTT** : press-to-talk = maintenir (souris / tactile / clavier). Mode bascule « un appui = je parle / un appui = j'arrête » proposé en alternative.
- **Raccourci** : un seul raccourci global, choisi par l'utilisateur parmi 2–3 propositions sûres, affiché en clair partout, modifiable à la voix (« change le raccourci »).
- **A11y (obligatoire, pas option)** : parcours complet sans voix (texte), sans souris (clavier seul, focus visible), sous-titres systématiques de ce que dit le modèle, contrastes suffisants, aucune étape timed. Erreur micro/caméra = proposition texte immédiate, jamais blocage.

## Config qui se masque / vidéo optionnelle

- **Fenêtre app** : visible étapes 1–4, se **masque** étape 6. Rappel : raccourci ou icône discrète. Jamais de « setup terminé » pompeux.
- **Fenêtre vidéo** : jamais imposée, jamais nécessaire au fonctionnement. Si activée : douce, petite, persistante, masquable d'un geste.

## Images

Optionnelles, ignorées pour ce sprint (pas de mockup ici).

## Non-objectifs (rappel)

Pas de code, pas de choix moteur, pas de spec touches exactes — ça, c'est le chantier Codex/design qui suit.
