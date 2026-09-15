---
date: 2026-09-14
type: design-app-onboarding
statut: design cible + tranche minimale implémentée
surface: native/presence
---

# Design app + onboarding — hyper-ambient

## Promesse

La première ouverture doit donner une seule certitude : « je sais comment lui parler ». La configuration n'est pas la destination. Elle prépare le PTT, laisse une trace textuelle accessible, puis se masque. La présence vocale reste le produit ; la vidéo est un supplément explicite.

## Flux de première ouverture

```text
Ouverture
  → Bienvenue
  → Choix du raccourci PTT
  → Vue de conversation
  → Masquer la configuration
  → Application réduite dans la barre des tâches
```

L'onboarding précède la connexion au micro et au serveur. Hermes peut donc être arrêté sans empêcher de lire ni de terminer les deux écrans. Après « Commencer », la vue conversation apparaît et le canal vocal tente de se connecter avec ses erreurs habituelles, affichées en texte.

## Écrans

### 1. Bienvenue

- Titre : « Bienvenue ».
- Explication courte : présence vocale, deux réglages, pas de jargon moteur.
- Réassurance : aucun son n'est enregistré pendant la configuration.
- Action unique et focalisée : « Continuer ».

### 2. Appuyez pour parler

- Instruction opérationnelle : maintenir, parler, relâcher pour envoyer.
- Choix exclusif : `Espace` ou `Ctrl + Espace`.
- Le libellé dit honnêtement « dans l'application » : la tranche Tkinter actuelle ne capture pas une touche globale lorsque la fenêtre n'a pas le focus.
- Rappel accessibilité visible : Tab, Entrée, transcription et réponse texte.
- Action : « Commencer ». Elle persiste le choix et ouvre la vue conversation.

### 3. Conversation / configuration légère

- Bulle d'état, grand PTT, transcript « Compris », texte « Réponse », état de connexion.
- Bouton secondaire explicite : « Masquer la configuration ».
- Masquer réduit la fenêtre dans la barre des tâches. Le clic sur son icône est le geste de rappel fiable et natif.
- La croix ferme réellement l'application ; Échap conserve ce comportement historique.

## PTT et raccourci

Le PTT a une sémantique unique sur tous les moyens d'entrée : appui = écoute, relâchement = envoi. Souris, `Espace` ou `Ctrl + Espace` suivent les mêmes méthodes afin d'éviter des états divergents. Quand le bouton a le focus, maintenir Entrée fonctionne également.

Le raccourci choisi est enregistré dans `%LOCALAPPDATA%/hyper-ambient/presence.json` (repli `%APPDATA%`, puis dossier utilisateur). L'écriture passe par un fichier temporaire remplacé atomiquement. Une valeur inconnue ou un JSON invalide revient à `Espace` et relance l'onboarding si nécessaire.

Un véritable raccourci système, disponible fenêtre réduite, nécessite une couche Windows dédiée (`RegisterHotKey`) et la gestion des collisions. Il ne doit pas être simulé ni promis par Tkinter.

## Accessibilité

- Parcours complet des choix et actions avec Tab ; focus visible sur le PTT.
- Entrée active les boutons et peut être maintenue sur le PTT.
- Contrôles nommés par du texte visible, jamais par couleur ou icône seule.
- Instructions, statut, transcription et réponse disponibles en texte.
- Contraste clair sur fond sombre ; la couleur de la bulle complète le statut sans le remplacer.
- Aucune étape chronométrée et aucun micro requis pendant le wizard.
- L'erreur micro/serveur reste non bloquante et textuelle dans la vue principale.

Limite connue : Tkinter expose ses contrôles natifs, mais ne fournit ni région ARIA live ni association de label comparable au Web. Avant diffusion large, une passe NVDA/Windows Narrator doit vérifier l'ordre et les annonces réels.

## Configuration qui se masque

Le masquage est une réduction (`iconify`) et non une fermeture ni un `withdraw` invisible. Ce choix tient la promesse « se masque » tout en gardant un rappel compréhensible sans tray icon supplémentaire. Une future version pourra ajouter une icône de zone de notification et un raccourci système de rappel.

## Vidéo optionnelle

La vidéo n'entre jamais dans le chemin critique. Le choix cible vient après le premier PTT réussi : « Petite présence visuelle » / « Voix seule », avec `Voix seule` par défaut. L'activation démarre l'overlay existant ; la désactivation l'arrête en un geste sans rouvrir toute la configuration.

Elle n'est pas câblée dans la tranche minimale actuelle : démarrer un second processus, garantir son arrêt et persister son état mérite un lot séparé. Aucun placeholder trompeur n'est affiché.

## Critères de recette

- Sans fichier de préférence, l'app montre Bienvenue avant toute tentative audio.
- Le wizard est terminable au clavier seul.
- Le choix de raccourci survit à une relance.
- PTT souris, raccourci choisi et Entrée focalisée partagent appui/relâchement.
- « Masquer la configuration » réduit la fenêtre ; l'icône de barre des tâches la rappelle.
- Hermes arrêté n'empêche pas le wizard ; son indisponibilité est ensuite visible en texte.
- `--onboarding` permet de rejouer le parcours sans supprimer les préférences.

## Hors périmètre de cette tranche

Images, samples voix, raccourci Windows global, tray icon, mode PTT bascule et orchestration vidéo. Aucun changement Docker ou Hermes.
