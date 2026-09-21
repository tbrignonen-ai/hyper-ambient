# Ronde GitHub — premier incrément

Ce flux relève en lecture seule les tickets GitHub ouverts, écarte les demandes de fusion et les sujets hors seuil, puis produit un état lisible des sujets à préparer. Il ne crée aucune branche, demande de fusion ou commentaire.

## Importer

1. Ouvrez `http://127.0.0.1:5678` puis **Workflows** > **Import from File**.
2. Choisissez le fichier `automation\n8n\ronde-github-premier-increment.json`, dans votre clone du dépôt.
3. Ouvrez chacun des nœuds **Vérifier l’accès GitHub** et **Relever les tickets ouverts**, puis choisissez le même identifiant n8n de type **GitHub API**, avec un jeton GitHub en lecture seule sur le dépôt. Le flux ne contient aucun jeton.
4. Dans **Paramètres**, passez `activer_github` à vrai après avoir choisi cet identifiant. Enregistrez le flux puis activez-le.

## Réglages

- La périodicité se change directement dans le nœud **Déclencheur planifié**. Il est réglé par défaut sur une fois par semaine, le lundi à 02:00.
- Tous les autres réglages sont au début du flux, dans le nœud **Paramètres** : dépôt, maximum de sujets, ancienneté, libellés exclus et libellés éligibles. `activer_github` permet de garder le chemin sans accès GitHub silencieux pendant la configuration.

Le comportement tant que l’accès GitHub n’est pas activé, ou sans ticket éligible, est silencieux : aucun élément n’est produit en sortie.

Le nœud **Déclenchement par un autre flux** est réservé à une exécution technique par un workflow parent ; la ronde hebdomadaire reste déclenchée par **Déclencheur planifié**.
