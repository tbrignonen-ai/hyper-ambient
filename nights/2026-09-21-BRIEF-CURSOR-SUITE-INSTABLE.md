# Nuit A6 — la suite plante l'interpréteur quand les fichiers Tk tournent ensemble

Tes trois correctifs sont bons : pris isolément, chacun des six fichiers passe. Mais en
vérifiant, j'ai trouvé plus grave que ce que je t'avais signalé. Périmètre :
`dev/tests/`, `native/presence/`. Aucune commande git.

## Le fait, reproduit

Chaque fichier, seul, est vert :

    test_presence_onboarding   => 24 passed
    test_presence_premier_tour =>  2 passed
    test_taquet_produit        =>  8 passed
    test_taquet_wire2          => 15 passed
    test_reglages_ui           => 56 passed   (trois exécutions de suite, vertes)
    test_raccourcis_windows    => 13 passed

Les six ensemble, en revanche, sont instables. Trois exécutions successives de la même
commande donnent trois résultats différents :

    essai 1 => 2 failed, 116 passed
    essai 2 => plantage de l'interpréteur (exit 3)
    essai 3 => plantage de l'interpréteur (exit 3)

Le plantage n'est pas un échec de test, c'est un arrêt brutal :

    Windows fatal exception: code 0x80000003

Et il tombe toujours au même endroit :

    dev/tests/test_reglages_ui.py::test_menu_voix_vient_du_serveur_pas_du_code

Le même test passe quand son fichier tourne seul. Ce qui le tue, c'est donc **l'état
laissé par les fichiers précédents**, pas son propre contenu.

## Ce que je te demande

Trouve la cause racine, ne mets pas le test de côté et ne le marque pas comme instable.
Une exception fatale 0x80000003 dans un processus Python vient presque toujours de la
couche native — ici, selon toute vraisemblance, de Tk : plusieurs racines `Tk()` créées
dans le même processus, une racine détruite mais encore référencée, des variables
`StringVar` rattachées à une racine morte, ou un `mainloop`/`update` appelé après
destruction.

Deux questions à trancher, et dis-moi la réponse dans ton rapport :

1. **Est-ce que la fuite est dans les tests ou dans le produit ?** Si `reglages_ui.py` ou
   `app.py` gardent une racine Tk, une image ou une variable au niveau du module, alors ce
   n'est pas seulement un problème de suite : deux ouvertures successives de la fenêtre de
   réglages dans une même session pourraient tomber sur le même défaut. C'est la
   possibilité qui m'inquiète, parce que l'utilisateur ouvrira ses réglages plusieurs fois.
   Vérifie-le explicitement en ouvrant et fermant la fenêtre plusieurs fois de suite.
2. Si la fuite est côté tests, isole-la proprement — une fixture qui crée et détruit la
   racine, et qui garantit qu'aucune référence ne survit au test.

## Ce que je ne veux pas

Ni `pytest.mark.skip`, ni `xfail`, ni réordonnancement des fichiers pour éviter la
combinaison qui plante, ni exécution en sous-processus pour masquer le symptôme. Le dépôt
devient public ce matin : une suite qui plante une fois sur trois est un signal que
quelque chose de réel ne va pas, et le fondateur a posé la règle — « tout doit marcher,
rien ne doit être douteux ».

## Vérification attendue

Sur l'hôte Windows, la commande exacte, **cinq fois de suite**, et colle les cinq lignes
de résultat :

    python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_premier_tour.py \
      dev/tests/test_taquet_produit.py dev/tests/test_taquet_wire2.py \
      dev/tests/test_reglages_ui.py dev/tests/test_raccourcis_windows.py -q -p no:cacheprovider

Cinq exécutions vertes, sans plantage. Puis la suite du conteneur pour la non-régression.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-SUITE-INSTABLE.md`, avec ta réponse à la
question 1 — produit ou tests.
