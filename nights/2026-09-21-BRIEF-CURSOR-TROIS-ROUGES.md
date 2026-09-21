# Nuit A5 — trois tests rouges sur l'hôte Windows, avant le push

Le dépôt part en public ce matin. Trois tests échouent **sur l'hôte Windows** — le
conteneur ne les voit pas, faute de `tkinter`. Deux sont des tests devenus faux, un est un
vrai défaut. Périmètre : `dev/tests/`, `native/presence/reglages_ui.py`,
`packaging/windows/README.md`. Aucune commande git.

Sortie réelle :

    python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_premier_tour.py \
      dev/tests/test_taquet_produit.py dev/tests/test_taquet_wire2.py \
      dev/tests/test_reglages_ui.py dev/tests/test_raccourcis_windows.py -q

    FAILED dev/tests/test_reglages_ui.py::test_les_trois_etats_ont_trois_couleurs_differents
    FAILED dev/tests/test_raccourcis_windows.py::test_script_pointe_vers_le_bat_avec_repertoire_de_travail
    FAILED dev/tests/test_raccourcis_windows.py::test_readme_tient_en_dix_lignes_et_reste_honnete
    3 failed, 113 passed, 1 skipped

## 1. Un vrai défaut — les trois états des sondes n'ont pas trois couleurs

    test_les_trois_etats_ont_trois_couleurs_differents

Un autre agent a repris les sondes de configuration cette nuit pour qu'elles distinguent
honnêtement trois états : joignable et répond / joignable mais ne répond pas / injoignable.
Le test dit que deux de ces états partagent la même couleur.

Ce défaut compte plus que son test : la raison d'être de ces trois états est qu'un voyant
vert qui ne prouve rien est pire que pas de voyant. Si deux états se ressemblent à l'œil,
la distinction n'existe pas pour l'utilisateur.

Donne-leur trois couleurs réellement distinctes, **et vérifie le contraste** : le dépôt
porte déjà un test d'accessibilité (`test_palettes_a11y_respectent_wcag_non_textuel`) qui
impose un rapport minimal pour les éléments non textuels. Une couleur qui passe le test
d'unicité mais échoue celui de contraste ne vaut rien. Fais passer les deux.

## 2. Un test devenu faux — le raccourci pointe vers le lanceur

    test_script_pointe_vers_le_bat_avec_repertoire_de_travail
    assert "hyper-ambient.bat" in script

Le raccourci appelle désormais `packaging\windows\lancer.ps1`, et c'est voulu : le lanceur
vérifie Docker, le conteneur, les serveurs de modèles et le host-agent avant d'ouvrir
Presence, là où le `.bat` lançait Presence à l'aveugle.

Mets le test à jour sur la nouvelle cible. **Garde ce qu'il protégeait vraiment** : que le
raccourci porte un répertoire de travail correct, et qu'il fonctionne depuis n'importe où.
Ajoute, tant que tu y es, une vérification que le script des raccourcis est en UTF-8 avec
BOM ou en ASCII strict — un `.ps1` sans BOM contenant des accents est illisible pour
Windows PowerShell 5.1, qui est le shell que lancent les raccourcis, et c'est un défaut
qu'on a déjà payé cette nuit.

## 3. Un test devenu faux, mais dont l'intention doit survivre

    test_readme_tient_en_dix_lignes_et_reste_honnete
    assert 87 <= 10

`packaging/windows/README.md` fait maintenant 87 lignes : c'est devenu un vrai guide
d'installation, ce qui est un progrès pour un dépôt public.

Mais la contrainte de dix lignes protégeait une exigence du fondateur, formulée ainsi :
« il faut le minimum, même sur un GitHub ». Ce qu'elle voulait dire, c'est que quelqu'un
qui arrive doit trouver **tout de suite** la poignée de commandes à taper, sans lire un
guide.

Ne supprime donc pas le test : **change ce qu'il vérifie.** Le fichier doit commencer par
un démarrage rapide d'au plus dix lignes, avant la première section détaillée, et ce
démarrage rapide doit contenir les commandes complètes, en PowerShell, avec les chemins
entre guillemets. Le reste du guide vient après. Réécris le début du README en conséquence
si nécessaire.

## Vérification attendue

Sur l'hôte Windows, et colle la sortie :

    python -m pytest dev/tests/test_presence_onboarding.py dev/tests/test_presence_premier_tour.py \
      dev/tests/test_taquet_produit.py dev/tests/test_taquet_wire2.py \
      dev/tests/test_reglages_ui.py dev/tests/test_raccourcis_windows.py -q

Puis la suite du conteneur, pour la non-régression.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-TROIS-ROUGES.md`.
