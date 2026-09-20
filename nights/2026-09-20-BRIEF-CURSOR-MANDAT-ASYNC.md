# Brief — Sortir l'appel harnais du tour de parole (mandat asynchrone)

Bonjour, je suis Opus et je travaille pour Human IA. Merci d'avance.

## Le probleme, mesure

Quand l'utilisatrice dit « demande a Codex de relire transport.py », le tour de
parole reste bloque **39 secondes**. Pendant ce temps hyper-ambient est muette
et l'application parait plantee. Ce n'est pas un probleme d'UX a habiller avec
du remplissage vocal : c'est un defaut d'architecture. L'appel reseau est
synchrone dans le tour. Il faut l'en sortir.

## L'architecture cible : le mandat en trois temps

Un appel a un harnais n'est plus une reponse, c'est un **mandat** confie.

1. **Accuse immediat**, avant toute latence reseau. Une phrase, tout de suite :
   « Je demande a Codex de relire transport.py. Je te previens. » Puis elle rend
   la main et la conversation continue normalement. **Pas de « patiente »,
   aucun son d'attente, aucun remplissage.**
2. **Pendant** : silence total. Un seul rappel spontane a 60 secondes, et
   seulement si la conversation est silencieuse depuis.
3. **A l'arrivee** : « Codex a fini », puis `resume_voix` (deux phrases
   maximum), puis **une seule** offre : « Tu veux le detail, ou que je te
   l'ouvre ? »

**Le texte long n'est jamais lu.** Jamais. Elle ne transporte qu'un resume court
et un pointeur vers la session du harnais, ou le detail existe deja.

## Perimetre — fichiers que tu peux modifier

- `src/brain/mandat.py` — **a creer**, le coeur du travail
- `dev/scripts/serve_hostagent.py` — le branchement
- `dev/tests/test_mandat.py` — **a creer**
- `src/i18n/__init__.py` — les phrases des trois temps, **fr et en seulement**
  (l'espagnol est hors perimetre, decision de l'utilisateur)

## Fichiers INTERDITS

- `src/brain/contrat_harnais.py` et `dev/tests/test_contrat_harnais.py` : un
  collegue les ecrit **en ce moment meme**. Tu les **importes**, tu ne les crees
  ni ne les modifies sous aucun pretexte.
- `src/ears/jev_reflexe.py`, `native/hostagent/windows_audio.py`,
  `native/presence/app.py` : hors sujet, n'y touche pas.
- **Aucune commande git.** Ni `add`, ni `commit`, ni `branch`, ni `stash`.
  Opus relit le diff et commite lui-meme.

## L'API du module voisin (deja specifiee, ne la redefinis pas)

```python
from src.brain.contrat_harnais import envelopper, analyser, ReponseHarnais
# envelopper(question: str) -> str       # prefixe la question du contrat de sortie
# analyser(texte: str) -> ReponseHarnais # champs : verdict, resume_voix,
#                                        # detail_voix, resultat_complet, conforme
```

Si le fichier n'existe pas encore au moment ou tu ecris, **ecris quand meme
l'import tel quel** et ne fabrique pas de doublure permanente. Tes tests peuvent
monkeypatcher `analyser`.

## `src/brain/mandat.py` — ce qu'il doit contenir

- `@dataclass Mandat` : `identifiant: str`, `harnais: str` (« Codex » /
  « Claude »), `question: str`, `sujet: str` (le fragment prononcable qui sert
  a l'accuse, ex. « relire transport.py »), `depose_a: float`,
  `etat: str` (`en_cours` / `fini` / `echoue`), `reponse: Optional[ReponseHarnais]`.

- `class RegistreMandats` : depot en memoire, `deposer()`, `en_cours()`,
  `prets()` (ceux finis dont l'annonce n'a pas encore ete faite),
  `marquer_annonce(identifiant)`, `oublier(identifiant)`.
  Borne dure : **au plus 3 mandats en cours simultanement** ; au-dela, refuser
  avec une phrase prononcable plutot que d'empiler.

- `async def confier(registre, harnais, question, sujet, appel) -> Mandat` :
  cree le mandat, **retourne immediatement**, et lance `appel` (une coroutine
  qui fait reellement l'appel au pont) dans une tache de fond via
  `asyncio.create_task`. La tache enveloppe la question avec `envelopper()`,
  analyse le retour avec `analyser()`, remplit `mandat.reponse` et bascule
  l'etat. **Elle ne doit jamais laisser une exception remonter** : toute erreur
  devient `etat="echoue"` avec une phrase prononcable, jamais une trace.

- Un delai d'expiration genereux (**300 secondes**) : un harnais qui ne rend
  jamais rien doit finir en `echoue`, pas rester `en_cours` eternellement.

## Le branchement dans `serve_hostagent.py`

Aujourd'hui, `_registre_pour_tour` (ligne ~961) laisse les outils harnais dans
le registre quand `harnais_demande(prompt)` est vrai, et `run_tool_loop` les
appelle **dans le tour**. C'est exactement ce qu'il faut supprimer.

Nouvelle regle : **les outils harnais ne sont plus jamais dans le registre du
tour.** `_registre_pour_tour` les retire inconditionnellement.

A la place, **avant** l'appel au modele local : si `harnais_demande(prompt)` est
vrai, on depose un mandat et on repond par l'accuse immediat, sans consulter le
modele local du tout. L'accuse est **une phrase de gabarit i18n**, pas une
generation : il doit partir avant toute latence, et un 3B qui hesite trois
secondes ruinerait le seul point de cette refonte.

Pour l'annonce d'arrivee : expose une methode que la boucle de tours consulte
quand la parole est libre — **jamais** pendant une lecture audio en cours,
**jamais** au milieu d'un tour utilisateur. Le mandat pret attend son tour.

## Le pop de l'outil : jamais automatique

Voler le focus est la faute capitale d'un logiciel ambiant : l'utilisatrice a
peut-etre confie le mandat precisement pour ne pas avoir a regarder l'ecran.
Elle **n'ouvre jamais la fenetre du harnais d'elle-meme**. Un badge passif
« 1 resultat pret » suffit ; l'ouverture n'a lieu que sur demande explicite.

Contrainte technique a connaitre : **Windows refuse `SetForegroundWindow`**
depuis un processus qui n'a pas le focus. Si tu emets un evenement vers
l'interface, contente-toi d'un evenement de badge ; ne tente pas l'elevation de
fenetre dans ce lot.

## Verification attendue

`docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py`

Reference avant ton travail : **1277 passes, 5 echecs pre-existants**
(`test_c11_identity`, `test_presence_onboarding`, `test_presence_premier_tour`,
deux de `test_taquet_produit`). Ces cinq-la ne sont pas de ton fait ; n'essaie
pas de les reparer. Mais **aucun echec nouveau** ne sera accepte.

Ecris un compte rendu court dans `nights/2026-09-20-OUT-CURSOR-MANDAT-ASYNC.md` :
ce que tu as fait, la sortie exacte de pytest, et ce que tu n'as pas fait.
