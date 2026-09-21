# Ronde GitHub — premier incrément

Ce flux relève en lecture seule les tickets GitHub ouverts, écarte les demandes de fusion et les sujets hors seuil, puis produit un état lisible des sujets à préparer. Il ne crée aucune branche, demande de fusion ou commentaire.

## Importer

1. Ouvrez `http://127.0.0.1:5678` puis **Workflows** > **Import from File**.
2. Choisissez le fichier `"D:\BGB Training\MOTHER-dev\automation\n8n\ronde-github-premier-increment.json"`.
3. Dans l’environnement du conteneur n8n, définissez `GITHUB_TOKEN` avec un jeton GitHub en lecture seule sur le dépôt. Le flux ne contient aucun jeton ; il attend exactement cette variable d’environnement.
4. Enregistrez le flux puis activez-le lorsque le jeton est disponible.

## Réglages

- La périodicité se change directement dans le nœud **Déclencheur planifié**. Il est réglé par défaut sur une fois par semaine, le lundi à 02:00.
- Tous les autres réglages sont au début du flux, dans le nœud **Paramètres** : dépôt, maximum de sujets, ancienneté, libellés exclus et libellés éligibles.

Le comportement sans jeton, sans accès GitHub, ou sans ticket éligible est silencieux : aucun élément n’est produit en sortie.
