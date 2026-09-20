# BRIEF Codex — audit qualite du harnais de tests
Lead : Claude (Opus). 2026-09-20 ~19h40.

La suite compte ~1219 tests verts, et pourtant deux fonctionnalites majeures se
sont revelees cassees en conditions reelles aujourd'hui :
- le « mains libres » n'avait jamais ete construit (les tests validaient fidelement
  un comportement a deux appuis qui n'etait pas la fonctionnalite demandee) ;
- la recherche web etait morte (aucun test ne touche le reseau, par conception).

## Ta mission : AUDIT, PAS DE CORRECTION
Ne modifie AUCUN fichier de production ni de test. Tu produis un rapport.
N'execute AUCUNE commande git.

Reponds a ces questions, preuves a l'appui (chemins de fichiers, noms de tests) :
1. Quelles zones du produit ont une couverture en TROMPE-L'OEIL : beaucoup de tests
   unitaires sur des fonctions pures, aucun test du chemin d'execution reel ?
2. Liste les tests qui verifient la FORME (une constante, une chaine, la presence
   d'un symbole dans un fichier source) plutot que le COMPORTEMENT. Ce sont les
   plus dangereux : ils restent verts quand la fonction disparait.
3. Cinq tests d'integration manquants qui auraient attrape les pannes du jour.
   Decris-les ; ne les ecris pas.
4. `dev/tests/test_health_sondes.py` ne se collecte plus (`ModuleNotFoundError:
   handlers`). Depuis quand, et que faut-il pour le reparer ?
5. Les tests Presence exigent `tkinter`, absent du conteneur : ils y echouent
   silencieusement alors qu'ils passent sur l'hote. Comment rendre ce piege
   impossible a ignorer ? (Un « DONE » faux a deja ete rendu a cause de lui.)

Rapport dans `nights/2026-09-20-OUT-AUDIT-QUALITE-TESTS.md`. Sois concret et bref.
