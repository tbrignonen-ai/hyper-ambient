# BRIEF Cursor — prechauffage JeV + maintien de connexion
Date : 2026-09-20 ~18h10. Lead technique : Claude (Opus). URGENCE BGB.
Suite directe de la lane JEV-CONNEXION-UI que tu viens de livrer (53 tests verts).

## Perimetre STRICT — n'ecris QUE dans ces fichiers
- `src/ears/jev_reflexe.py`
- `dev/scripts/serve_hostagent.py`
- `dev/tests/test_jev_prechauffage.py` (a creer)

INTERDIT d'ouvrir ou modifier : `native/presence/app.py` (ta lane precedente, close),
`src/i18n/__init__.py`, `src/mouth/*`, `.env.local`.
INTERDIT : lancer Presence, commiter, creer une branche.

## Mesures etablies — ne PAS re-investiguer, c'est prouve
JeV appelle une API distante (typesafe.ai) pour decider si une phrase est adressee a
l'assistante. En mains libres, une reponse « pas adressee » fait ignorer le tour.

`JevReflexe` construit son transport httpx avec
`httpx.Limits(max_connections=1, max_keepalive_connections=1, keepalive_expiry=30.0)`
et un timeout plafonne a 600 ms (`MAX_TIMEOUT_MS`), applique DEUX fois : sur le post
httpx ET sur un `asyncio.wait_for` englobant.

Mesures reelles contre l'API :
- Poignee TLS a froid : 590 a 740 ms -> DEPASSE le budget de 600 ms.
- Consequence : l'appel expire, rend `None`, et comme le pool n'a qu'une connexion,
  la connexion cassee est jetee et l'appel suivant repart a froid. Cascade.
  Mesure a froid : 648 / 601 / 601 / 591 ms -> 3 expirations sur 4.
- Apres un prechauffage paye HORS budget (173 a 590 ms) : 269 / 247 / 293 / 247 ms,
  4 succes sur 4.
- Duree de vie de la connexion chaude, mesuree :
  0s ok · 5s ok · 15s ok · 25s ok · 35s ok · 60s ok (351 ms) · **90s EXPIRE (601 ms)**

Donc : un prechauffage unique NE SUFFIT PAS. Il faut un ping de maintien.

## Travail demande

### 1. `src/ears/jev_reflexe.py` — methode `prechauffer()`
Ajoute une coroutine publique `async def prechauffer(self) -> bool` qui :
- obtient le transport via `_get_transport()` ;
- fait UNE requete jetable vers `self.endpoint` avec un timeout GENEREUX
  (10 s, explicitement PAS `self.thresholds.timeout_ms`) — le but est de payer la
  poignee TLS hors du budget du tour ;
- avale toute exception et toute reponse : le contenu ne nous interesse pas, seule la
  connexion compte ;
- rend `True` si la connexion semble etablie, `False` sinon. Ne leve jamais.
- Si la cle est absente (`_key_at_execution()` vide), rend `False` immediatement sans
  requete — le repli silencieux doit rester silencieux.

### 2. `src/ears/jev_reflexe.py` — maintien
Ajoute `async def maintenir(self, intervalle_s: float = 40.0)` : une boucle qui appelle
`prechauffer()` toutes les `intervalle_s` secondes jusqu'a annulation. 40 s est choisi
parce que 60 s tient encore et 90 s non ; garde cette valeur en constante nommee avec un
commentaire citant la mesure. La boucle doit se terminer proprement sur
`asyncio.CancelledError`.

### 3. `dev/scripts/serve_hostagent.py` — cablage
Dans `on_options` (vers la ligne 616), quand `mains_libres` passe a True :
- demarrer une tache asyncio qui fait `prechauffer()` puis lance `maintenir()` ;
- quand le prechauffage est fini, envoyer au client Presence le message
  `{"type":"jev_pret"}` — Presence l'attend deja, Cursor l'a cable cet apres-midi et le
  teste (`dev/tests/test_presence_connexion_jev.py`). Ne change pas ce nom de message.
- quand `mains_libres` repasse a False, ANNULER la tache de maintien.
- ne jamais demarrer deux taches de maintien en parallele.
Journalise `JEV   : prechauffage ok en N ms` / `JEV   : maintien arrete`.

## Tests — `dev/tests/test_jev_prechauffage.py`
AUCUN appel reseau reel. Injecte un faux transport (le constructeur de `JevReflexe`
accepte deja un transport injecte, regarde `_owns_transport`). Couvre au minimum :
- `prechauffer()` sans cle -> rend False, aucune requete emise
- `prechauffer()` avec faux transport -> rend True, et le timeout passe a la requete est
  bien ~10 s et PAS 0,6 s (c'est le coeur du correctif : verifie-le explicitement)
- `prechauffer()` quand le transport leve -> rend False, ne propage pas
- `maintenir()` appelle `prechauffer` plusieurs fois puis s'arrete sur annulation
  (utilise un intervalle minuscule et `asyncio.wait_for` pour ne pas ralentir la suite)
- l'intervalle par defaut est < 60 s (la mesure interdit plus)

## Preuve a rendre
Les tests Python de ce depot tournent DANS le conteneur Docker `mother-core-dev`
(le host-agent y vit), sauf les tests Presence qui exigent tkinter et tournent sur l'hote.
Pour cette lane, lance DANS le conteneur :

    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_jev_prechauffage.py dev/tests/test_jev_reflexe.py dev/tests/test_jev_branchement.py"

Colle la sortie telle quelle dans `nights/2026-09-20-OUT-JEV-PRECHAUFFAGE.md`, avec le
diff resume et les difficultes. Ne reponds que OK.
