# Correctif bloquant — langue par défaut du host-agent

## Correctif livré

- `HA_LANG` absent, vide ou composé d'espaces retourne désormais sur `fr`.
- Une langue non prise en charge (par exemple `zz`) écrit un avertissement dans
  le journal et retourne sur `fr`, sans interrompre le démarrage.
- Le même repli sans exception couvre les lectures de configuration ajoutées
  dans `serve_hostagent.py` qui pouvaient casser le boot : backend EARS inconnu
  et réglages numériques audio malformés. Les chaînes vides utilisent aussi
  leur défaut pour EARS et MOUTH.
- Aucun fichier sous `native/presence/`, `src/i18n/` ou `src/onboarding/` n'a
  été modifié.

## Test de non-régression

Ajout de `test_boot_sans_ha_lang_retombe_sur_le_francais` : avec un
environnement sans `HA_LANG`, le chemin de boot se termine et fixe
`HA_LANG`, `HYPER_AMBIENT_LANG`, `EARS_LANGUAGE` et `MOUTH_LANGUAGE` à `fr`.
Ce test échouait avant le correctif car `_code_langue("")` levait un
`ValueError`. Un test distinct vérifie le repli journalisé pour `zz`.

Exécution ciblée après correction :

```text
docker exec mother-core-dev python -m pytest dev/tests/test_taquet_wire2.py -q
...............                                                          [100%]
15 passed in 0.49s
```

## Cycle de reproduction Docker

La seule ligne `HA_LANG` a été retirée de `.env.local`, sans afficher ni
réécrire les autres lignes, puis la commande demandée a été exécutée :

```text
docker exec mother-core-dev bash /workspace/dev/scripts/relance_hostagent.sh
carte figee: brain=llamacpp model=granite-4.2-3b-Q4_K_M.gguf ears=faster-whisper/large-v3 mouth=magpie/Sofia/cuda
langue: fr
host-agent relance, pid 17787
host-agent pret, pid 17787
```

Extrait vérifié du journal du host-agent :

```text
LANG  : fr (prompt/nombres ; carte ASR/TTS=fr/fr)
écoute sur 0.0.0.0:8001 /hostagent
```

La ligne unique `HA_LANG=fr` a ensuite été remise à la fin de `.env.local`.
Vérification : une seule ligne `HA_LANG`, elle vaut `fr` et elle est la
dernière ligne du fichier.

## Vérification intégrale

```text
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
4 failed, 1439 passed, 61 skipped, 2 xfailed, 41 warnings in 20.60s
```

Les quatre échecs sont inchangés et pré-existants :

- `test_orbe_repos_reste_lisible`
- `test_un_appui_deja_relache_est_invisible_pour_la_boucle`
- `test_assurer_stdio_pythonw_ecrit_dans_un_journal`
- `test_palettes_a11y_respectent_wcag_non_textuel`

Ils échouent tous sur `ModuleNotFoundError: No module named 'tkinter'` dans le
conteneur. Le total de passes est 1439 plutôt que la référence 1437 car ce lot
ajoute deux tests de langue, tous deux passants. Aucun échec nouveau.
