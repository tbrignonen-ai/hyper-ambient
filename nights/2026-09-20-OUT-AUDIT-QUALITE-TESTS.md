# Audit qualité du harnais de tests — 20 septembre 2026

Audit en lecture seule. Aucune commande Git exécutée.

## 1. Couverture en trompe-l'œil

### Recherche Web : forte couverture de l'adaptateur, aucune du service réellement utilisé

`dev/tests/test_tools_web.py` annonce explicitement « sans réseau » et emploie
`FakeHTTPClient`; `dev/tests/test_tavily_mock_only.py` annonce qu'aucun test
n'ouvre de socket. Ils testent bien la sérialisation, les réponses, et les replis
*simulés*, mais jamais DNS/TLS/HTTP, les identifiants effectifs, ni l'instance
SearXNG configurée. Or le chemin réel conditionne même l'exposition de l'outil :
`dev/scripts/serve_hostagent.py:404-423` ne fait `register_web_search` que si un
client et `SEARXNG_URL` ou une clé sont présents. Aucun test ne construit ce
registre avec la configuration d'exécution, et aucun ne joint un fournisseur.

### Mains libres / Presence : UI et décisions testées, parcours vocal réel absent

`dev/tests/test_presence_mains_libres.py` teste la configuration, le wizard et
`jev_doit_ignorer` avec un objet d'évaluation fabriqué. `test_presence_stop_mains_libres.py`
teste les actions de bouton et `SessionVocale._boucle_tours` avec `Capture` et
`Ws` factices. Le chemin produit est autrement plus long :
`Application.enfoncer`/`relacher` → `SessionVocale._boucle_tours_continus`
(`native/presence/app.py:590-755`) → capture continue → WebSocket →
`HostPipeline.on_options`/`on_frames` (`dev/scripts/serve_hostagent.py:1465-1471`)
→ EARS/JeV → réponse audio. Aucun test ne le traverse. En particulier, aucun
test ne prouve qu'une première prise de parole, sans seconde pression, parvient
au host-agent et produit une réponse.

### Transport host-agent : intégration ASGI interne, pas déploiement réel

`dev/tests/test_hostagent_transport.py` est utile, mais son serveur est le
`TestClient` Starlette et l'adresse est forcée par `_adresse_de_test()` à
`127.0.0.1`. Cela ne couvre ni uvicorn, ni son implémentation WebSocket choisie
en production (`HOSTAGENT_WS_IMPL`, `dev/scripts/serve_hostagent.py:1518`), ni
le client Presence, ni le cycle de vie de deux processus.

### Audio et moteurs : unités isolées des dépendances d'exécution

`dev/tests/test_windows_audio.py` injecte un faux flux; `test_mouth_magpie.py`
injecte `FauxMoteur`; les tests de TTS distante injectent leurs clients. Ces
tests verrouillent des contrats locaux, pas l'ouverture du micro, le pilote,
le chargement de modèle, ni le passage audio de bout en bout.

## 2. Tests de forme dangereux

Les assertions ci-dessous regardent le texte ou l'AST du source. Elles ne
démontrent pas que la responsabilité est exercée; une constante/commentaire ou
un symbole mort peut les laisser vertes.

| Test | Forme vérifiée | Risque concret |
|---|---|---|
| `test_hostagent_channel.py::test_la_comparaison_du_secret_utilise_compare_digest` | `inspect.getsource`, présence de `hmac` et `compare_digest` | l'appel peut ne jamais protéger l'authentification. |
| `test_hostagent_channel.py::test_le_canal_ne_transporte_que_les_primitives_du_contrat` | présence textuelle de `is_permitted` | heureusement complété par des appels comportementaux dans le même test; la partie source reste redondante et fragile. |
| `test_hostagent_transport.py::test_seules_les_primitives_du_contrat_sont_acceptees` | présence de `is_permitted` | idem : le scénario WebSocket est la preuve utile, pas cette ligne. |
| `test_mouth_magpie.py::test_hostagent_branche_magpie` | chaînes `elif backend == "magpie"` et `chargement magpie` dans `serve_hostagent.py` | le backend peut ne jamais être instancié au démarrage réel. |
| `test_remote_tts.py::test_module_ne_peut_pas_charger_un_gpu_local` | absence de sous-chaînes dans `remote_tts.py` | un import indirect ou un chemin exécuté peut charger le GPU. |
| `test_reveil_court.py::test_decision_est_une_fonction_pure` | absence de `print(`/`asyncio`/`websocket` dans une fonction | ne prouve ni l'absence d'effet indirect ni le câblage. |
| `test_reveil_court.py::test_cablage_apres_jev_en_mains_libres_seulement` | recherche et ordre de chaînes dans `serve_hostagent.py` | les fonctions peuvent être mortes ou appelées avec le mauvais état. |
| `test_secours.py::test_le_module_est_une_fonction_de_decision_pure` | absence de chaînes dans le module | même faux sentiment de pureté. |
| `test_warmup.py::test_rapport_contient_les_durees...` et `...signal_synthetique...` | `monotonic` et interdits recherchés dans le source | l'observation runtime déjà présente est la vérification pertinente; ces lignes ne la renforcent pas. |
| `test_windows_audio.py::test_le_module_s_importe_sans_peripherique_audio` | AST des imports, absence de `sounddevice` au niveau module | ne teste pas l'import paresseux au moment de l'ouverture réelle. |
| `test_talk_diagnostic_wasapi.py::test_argparse_api_accepte_wasapi` | quatre noms de backend dans le source de `talk.main` | ne prouve ni parsing ni sélection du périphérique. |
| `test_tool_loop_h_edges.py::test_smoke_script_cible_ipv4_alias_lfm_sans_kill` | chaînes et interdits dans un script | le script peut être non exécutable ou ne jamais atteindre la cible. |
| `test_world_port.py::test_port_n_importe_ni_mouth_ni_ears_ni_brain_ni_torch` et `test_world_recette.py::test_recette_n_importe_ni_torch_ni_hostagent_ni_ears` | AST des imports | utile comme garde d'architecture, mais pas comme test de l'isolation runtime (imports dynamiques exclus). |

## 3. Cinq tests d'intégration manquants

1. **Mains libres, un seul déclenchement, chemin complet.** Démarrer le vrai
   serveur ASGI/uvicorn sur un port libre et une `SessionVocale` réelle avec
   capture synthétique. Activer `mains_libres`, injecter parole puis silence,
   et vérifier : une ouverture de capture continue, trames reçues par
   `HostPipeline`, EARS appelé, et au moins une trame de réponse lue. Aucun
   second appui ne doit être requis.
2. **Propagation de l'option sur le vrai WebSocket.** Connecter Presence au
   serveur réellement lancé, basculer OFF→ON puis ON→OFF, et observer dans le
   pipeline `on_options` et le comportement de capture correspondant. Cela
   couvre le message `options`, son ordre après `hello`, et le processus qui
   consomme vraiment le flag.
3. **Registre Web au démarrage du host-agent.** Avec une configuration
   d'exécution minimale valide (`SEARXNG_URL` ou clé) et un vrai
   `httpx.AsyncClient`, instancier `HostPipeline`/`construire_registre` puis
   vérifier que `web_search` est exposé au modèle. Le test doit échouer si la
   configuration réelle ou le câblage retire silencieusement l'outil.
4. **Sonde Web externe opt-in.** Job séparé, secret de test et coût borné :
   appel HTTP réel vers le fournisseur configuré, sur une requête stable, avec
   assertion « réponse exploitable » (ni `_NO_KEY`, `_NO_CLIENT`, `_FAILED`,
   ni `_EMPTY`). Il détecte DNS, TLS, clé révoquée, changement d'API et panne
   du fournisseur. Ne pas le mélanger aux unités hermétiques.
5. **Repli Web sur sockets réelles.** Faire tomber le SearXNG configuré (port
   local fermé) et fournir un fournisseur de secours de test accessible par
   HTTP réel; lancer la boucle d'outil via le registre du host-agent et vérifier
   la réponse parlable. Cela couvre le repli qui existe aujourd'hui uniquement
   derrière `FakeHTTPClient`.

## 4. `test_health_sondes.py`

Le problème décrit ne se reproduit **pas** dans l'état audité :
`python -m pytest --collect-only -q dev/tests/test_health_sondes.py` collecte
3 tests. La cause de `ModuleNotFoundError: handlers` est donc absente ici.
Preuve : `dev/tests/test_health_sondes.py:14-17` ajoute explicitement
`workers/night_health_vault_note` à `sys.path`, et ce dossier contient
`handlers.py`.

Il est impossible de dater une panne antérieure sans historique, et la consigne
interdit Git. Les seules dates vérifiables du système de fichiers sont le
19-09-2026 14:17 pour le test, et 14:18 pour `handlers.py`; elles établissent
un état fonctionnel au plus tard à cette date, pas la date d'apparition ni de
réparation. Pour le rendre durable : transformer le worker en paquet importable
(`workers/night_health_vault_note/__init__.py`) et importer
`workers.night_health_vault_note.handlers`, ou installer ce paquet dans
l'environnement de test; supprimer ensuite la mutation locale de `sys.path`.

## 5. Tkinter absent du conteneur : rendre le piège visible

Le piège est réel et répété : `test_presence_interruption.py:14`,
`test_presence_stop_mains_libres.py:12` et `test_presence_connexion_jev.py:6`
font `pytest.importorskip("tkinter")`; les autres fichiers Presence convertissent
`ModuleNotFoundError` et `tk.TclError` en `pytest.skip` (par exemple
`test_presence_mains_libres.py:109-119`). `make test` exécute précisément
`docker exec ... pytest dev/tests -v` (`Makefile:23-24`). Un vert peut donc
inclure l'absence complète de ces scénarios.

Mettre en place deux lanes explicites :

* **unités conteneur** : exclure par marqueur `presence_ui`, et publier le
  nombre de skips comme information, jamais comme preuve de recette;
* **recette Presence obligatoire** : image/job desktop doté de Tk/Tcl et d'un
  affichage (Windows hôte ou Xvfb), exécutant `pytest -m presence_ui -rs`.
  Dans cette lane, la fixture `require_tk` doit faire `pytest.fail` si tkinter
  ou `Tk()` est indisponible — jamais `skip`.

Le pipeline doit échouer si cette lane n'est pas exécutée, si elle collecte zéro
test, ou si elle produit un skip Tk. Le résumé final doit annoncer séparément
`passed / failed / skipped` par lane et interdire un statut « DONE » lorsque
`presence_ui` n'a pas passé. Une règle CI de contrôle du rapport (ou un petit
script) peut traiter `SKIPPED.*Tk indisponible` comme une erreur dans cette lane.
