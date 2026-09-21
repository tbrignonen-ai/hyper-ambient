# Compte rendu de peaufinage

Les deux fichiers `_COMPLETE.docx` ont été repris sans toucher aux deux originaux.

## Changements effectués

- Le dossier technique décrit maintenant les deux canaux de raisonnement : modèle local de 3 milliards de paramètres pour les tours ordinaires, classifieur local à chaque tour, puis canal distant pour les demandes difficiles.
- Les mesures fournies ont été placées dans le plan de tests et dans la préparation de soutenance : 650 ms pour un tour local ordinaire et 2,2 secondes pour un tour qui confie une tâche à Codex.
- Le chemin de bout en bout du pilotage des harnais est décrit : demande orale, appel d'outil, mandat déposé, puis réponse annoncée sans bloquer l'échange.
- Le stockage local des conversations en clair, lisibles par l'utilisateur et sans sortie de la machine, est ajouté aux flux, aux risques et aux réponses de soutenance.
- Le scénario de panne porte bien sur une situation utilisateur plausible : micro rendu muet parce qu'une autre application l'utilise. La détection, le message utile, les gestes de reprise et le contrôle du retour du signal sont décrits.
- La limite du produit est assumée dans les deux documents : le pilotage des harnais sert à des tâches simples ; il ne remplace pas Codex ou Claude Code pour du développement intensif.
- macOS est signalé comme portage écrit mais non essayé sur une machine réelle, donc non présenté comme supporté.
- Le déroulé d'oral est réaligné sur une réponse locale, l'alerte micro, puis une tâche confiée au canal distant.

## Cases ou vérifications encore ouvertes

- Nom complet et cohorte du candidat.
- Rejouer et dater le flux Camunda complet.
- Relancer la non-régression sur le poste de soutenance.
- Vérifier l'accessibilité avec un lecteur d'écran.
- Valider la recherche sur un réseau réel.
- Relire l'historique récent avant de compléter le journal de versions.

## Point à trancher par le fondateur

Le dossier contient déjà des captures et des références à l'interface Presence. La nouvelle limite indique que le pilotage des harnais de développement n'a pas d'interface visuelle. Pour ne pas contredire les captures, cette limite a été formulée comme l'absence d'interface visuelle dédiée pour ce volet de développement. Si l'absence d'interface visuelle concerne au contraire tout hyper-ambient, il faut retirer ou remplacer les captures et les passages sur l'écran de réglages avant dépôt.
