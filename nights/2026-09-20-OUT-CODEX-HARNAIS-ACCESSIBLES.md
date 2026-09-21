# Harnais Codex et Claude accessibles dans le tour vocal

## Résultat

`ask_codex` et `ask_claude` sont de nouveau présents dans le registre envoyé
au modèle à chaque tour. Il n'existe plus de filtrage par expression régulière
ni de chemin vocal qui décide à la place du modèle.

Quand le modèle appelle l'un de ces outils, son handler dépose immédiatement
un mandat dans `RegistreMandats`, lance le pont dans sa tâche de fond, puis
rend l'accusé : « Je demande à Codex. Je te préviens dès qu'il répond. » Le
flux vocal s'arrête après cet accusé : aucun second aller-retour BRAIN, et
aucune attente du pont ne peut geler le tour.

L'annonce de résultat demeure inchangée : la veille appelle
`annoncer_mandats_prets`, synthétise l'arrivée, puis envoie son marqueur vide
de fin de tour. Le test de transport autonome de cette annonce reste vert.

## Changements

- Suppression de `harnais_demande` et de ses tests fondés sur une liste de
  verbes.
- Ajout du dépôt asynchrone partagé dans `src/brain/mandat.py` et de handlers
  de mandat pour Codex et Claude.
- Le serveur construit le registre avec son registre de mandats et ne retire
  plus aucun outil dans `_registre_pour_tour`.
- Test de bout en bout : un appel modèle à `ask_codex` crée un mandat, retourne
  en moins d'une seconde malgré un pont simulé à 30 secondes, et ne redemande
  pas une réponse au modèle.
- Prompt renforcé de façon générale : une question sur une capacité doit
  employer l'outil correspondant pour la démontrer ou la vérifier, sans règle
  codée sur des mots-clés.

## Vérification

Commande exécutée :

```text
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat : **1400 passed, 36 skipped, 2 xfailed, 4 failed**.

Les quatre échecs sont hors périmètre et préexistants : ils importent
`native/presence` dans le conteneur, où `tkinter` n'est pas installé
(`test_presence_onboarding`, `test_presence_premier_tour`, deux tests de
`test_taquet_produit`). Aucun échec nouveau relatif aux harnais, au socket ou
au prompt n'a été observé.
