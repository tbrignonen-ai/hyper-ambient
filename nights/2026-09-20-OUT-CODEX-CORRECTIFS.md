# Correctifs urgents — 20 septembre 2026

## Corrigé

1. Décalage socket des mandats — serveur uniquement

Chaque annonce d'arrivée de mandat et chaque rappel clôt maintenant son propre
tour audio par un marqueur vide audio.render. L'annonce qui suit la fin d'un
tour de conversation ne peut donc plus laisser de trames orphelines au début du
tour suivant. Le test test_annonce_arrivee_est_un_tour_transport_autonome
simule précisément cette séquence.

2. Mémoire conversationnelle

MEMOIRE_MESSAGES est porté de 6 à 12 : six échanges sont conservés. Les
résultats d'outils sont copiés dans l'historique du premier tour qui les suit,
puis _dernier_outils est vidé avant cette requête : ils ne sont donc pas
réinjectés indéfiniment. Le test
test_le_resultat_outil_expire_apres_le_tour_de_suivi couvre le troisième tour.

Mesure TTFT directe sur llama.cpp local (même processus, historique synthétique
de même forme) : à chaud, 6 messages = 29 ms puis 23 ms ; 12 messages = 24 ms
puis 22 ms. Pas de dégradation observée. Les premières requêtes, non
comparables car froides, ont mesuré 285 ms (6) et 90 ms (12).

3. Outil sur question méta / actualité

Le prompt système local français et anglais impose désormais d'utiliser un
outil disponible pour vérifier une information, notamment l'accès au web et
toute réponse dépendant de faits actuels ou susceptibles d'avoir changé. C'est
une instruction sémantique du prompt, sans règle de mots-clés côté code. Le
test test_local_prompt_outils.py vérifie le prompt réellement injecté dans la
requête llama.cpp.

## Pytest

Commande exécutée après chacune des trois corrections :

~~~text
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
~~~

### Après le correctif socket

Sortie exacte du résumé pytest :

~~~text
5 failed, 1379 passed, 25 skipped, 2 xfailed, 39 warnings in 18.11s
~~~

Échecs : test_c11_identity, test_presence_onboarding,
test_presence_premier_tour, et les deux tests test_taquet_produit attendus.

### Après le correctif mémoire

Sortie exacte du résumé pytest :

~~~text
15 failed, 1378 passed, 32 skipped, 2 xfailed, 39 warnings in 18.53s
~~~

Les dix échecs supplémentaires venaient des fichiers Réglages/UI modifiés
concurremment (test_parite_anglaise et test_reglages_ui), en plus des cinq
échecs préexistants. Ils n'ont pas été corrigés ici, car src/i18n/__init__.py
et native/presence/app.py étaient explicitement interdits et en cours
d'édition par un collègue.

### Après le correctif prompt

Sortie exacte du résumé pytest :

~~~text
5 failed, 1389 passed, 32 skipped, 2 xfailed, 39 warnings in 18.25s
~~~

Échecs restants, exactement :

~~~text
FAILED dev/tests/test_c11_identity.py::test_cerveau_local_porte_identite_et_style_vocal
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
~~~

## Non fait

- Aucun changement client : le correctif socket est entièrement côté serveur.
- Aucun changement dans native/presence/app.py, src/i18n/__init__.py,
  src/onboarding/* ou native/hostagent/*.
- Les cinq échecs préexistants ne sont pas corrigés : l'un relève du contrat
  C11 existant, les quatre autres de tkinter absent du conteneur ou des modules
  Presence interdits.
- La mesure de latence est une mesure TTFT BRAIN locale, pas une mesure
  bout-en-bout EARS/TTS : elle isole exactement l'effet de l'historique.

