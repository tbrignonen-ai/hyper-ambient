---
date: 2026-09-21
heure: "03:10"
type: out
lane: onboarding-simple-et-sondes-honnetes
auteur: Qwen
surface: src/onboarding/sondes.py, native/presence/reglages_ui.py, dev/tests/test_onboarding_sondes.py, dev/tests/test_reglages_ui.py
related:
  - "[[2026-09-21-BRIEF-QWEN-ONBOARDING]]"
  - "[[2026-09-20-OUT-QWEN-VERIFICATION]]"
  - "[[2026-09-20-OUT-CURSOR-CHAMPS-EDITABLES]]"
  - "[[2026-09-20-OUT-CODEX-HARNAIS-ACCESSIBLES]]"
  - "[[2026-09-20-SPEC-ONBOARDING-V2]]"
---

# Qwen — l'onboarding simple marche, et ses sondes disent vrai

Réponse au brief `nights/2026-09-21-BRIEF-QWEN-ONBOARDING.md`.

**Verdict court.** Les sondes ne mentent plus : elles posent une vraie question
minimale, vérifient le corps de la réponse, et distinguent quatre états dont les
trois demandés. Je l'ai prouvé **contre les vrais ponts en marche**, pas
seulement contre des doubles : Codex et Claude ont réellement répondu `PONG`
(5,00 s et 2,32 s) et les deux voyants sont passés au vert. La fenêtre de
réglages s'ouvre, se saisit, s'enregistre et se relit ; les champs sont lisibles
(9,25:1) ; une installation vierge ne plante pas. Deux défauts supplémentaires
ont été trouvés en testant et corrigés. Sept constats hors périmètre sont à
transmettre, dont un qui concerne directement d'autres agents de cette nuit.

---

## 1. Périmètre respecté

Relevé par horodatage, le 2026-09-21 à 03:08 (aucune commande git exécutée).

### Fichiers que j'ai écrits

| Fichier | Taille | Lignes | Dernière écriture |
|---|---|---|---|
| `src/onboarding/sondes.py` | 32 784 o | 924 | **21/09 03:03:46** |
| `native/presence/reglages_ui.py` | 59 958 o | 1 774 | **21/09 02:44:18** |
| `dev/tests/test_onboarding_sondes.py` | 48 680 o | 1 407 | **21/09 03:04:04** |
| `dev/tests/test_reglages_ui.py` | 62 398 o | 1 728 | **21/09 02:45:34** |
| `nights/2026-09-21-OUT-QWEN-ONBOARDING.md` | — | — | ce rapport |

État initial mesuré en début de nuit : `sondes.py` 16 198 o (20/09 23:07),
`reglages_ui.py` 56 191 o (20/09 23:17), `test_onboarding_sondes.py` 28 000 o
(20/09 23:06), `test_reglages_ui.py` 50 729 o (20/09 23:15).

### Fichiers du périmètre que je n'ai PAS touchés

`src/onboarding/reglages.py` (20/09 21:16), `src/onboarding/__init__.py`
(20/09 21:01), `dev/tests/test_onboarding_reglages.py` (20/09 21:17),
`dev/tests/test_presence_onboarding.py` (20/09 23:15) — horodatages inchangés.
`test_presence_onboarding.py` teste `native/presence/onboarding.py` (le wizard de
premier lancement), qui n'est ni `src/onboarding/` ni `reglages_ui.py` : je l'ai
laissé à son propriétaire, voir §9.4.

### Fichiers interdits : lus, jamais écrits

| Fichier | Dernière écriture | Par qui |
|---|---|---|
| `dev/scripts/serve_hostagent.py` | 21/09 02:08:54 | un autre agent (passé de 89 425 à 97 128 o **pendant** ma nuit) |
| `dev/scripts/carte_figee.env` | 21/09 01:43:25 | un autre agent |
| `.env.local` | 21/09 00:01:50 | antérieur à mes écritures ; **lu seulment** |
| `README.md` | 21/09 02:06:11 | un autre agent |
| `src/i18n/__init__.py` | 20/09 23:16:08 | inchangé (voir §9.5) |
| `src/brain/tools_codex.py`, `tools_cli.py` | 20/09 22:18:30 | inchangés |
| `native/presence/app.py` | 20/09 23:48:41 | inchangé |
| `packaging/` | — | jamais ouvert |

`.env.local` n'a été ouvert qu'en lecture, par `lire_reglages`, pour récupérer
les deux adresses de pont et la **longueur** des jetons. Aucune valeur de jeton
n'a été affichée, journalisée ni recopiée ici. Le garde-fou existant
`test_reglages_ui.py::session_propre` compare le `st_mtime_ns` du vrai
`.env.local` avant/après chaque test : il est passé sur les 56 tests.

### Rien installé, nulle part

Aucun `pip install`. Tous les runs pytest sont passés par
`PYTHONDONTWRITEBYTECODE=1` et `-p no:cacheprovider`. Mes bancs de test ont été
écrits **hors du dépôt**, dans `C:\Users\thoma\AppData\Local\Temp\ha_e2e\`.

`.pytest_cache` du dépôt : dernier écrit le **25/08/2026 03:01**, non touché.

⚠ Des `.pyc` récents existent dans le périmètre (`sondes.cpython-311.pyc`
02:24:50, `reglages_ui.cpython-311.pyc` 02:25:24,
`test_onboarding_sondes.cpython-313-pytest-9.1.1.pyc` 01:50:20). J'ai mesuré
avant/après : un run conteneur avec les deux drapeaux **ne réécrit pas** ces
fichiers (02:24:50 → 02:24:50 après un run complet). Ils ne viennent donc pas de
mes commandes ; l'explication la plus probable est un pytest lancé sans drapeau
par un autre agent dans le même conteneur (`dev/`, `src/`, `native/` sont montés
en bind, donc il écrit sur le disque hôte). Je le signale plutôt que de le
passer sous silence.

---

## 2. Le défaut mesuré : pourquoi le vert ne prouvait rien

Le brief citait `sonder_codex` répondant `ok=True` en 13 ms. Voici la cause
exacte, vérifiée dans le code **et** sur le pont en marche.

L'ancienne sonde postait `{"question": ""}` et concluait sur le **statut HTTP
seul** :

```python
if statut == 200:
    return Sonde(service, True, _OK[service], latence)   # « Codex repond. »
```

Or les deux ponts rendent un **statut 200 pour tous les cas de figure**, y
compris l'échec total du harnais. `native/codexbridge/bridge.py:130` :

```python
if not question:
    return {"ok": False, "error": "question vide"}      # -> _send(200, ...)
```

Mesure du 2026-09-21 sur le pont en marche, question vide puis vraie question :

```
===== codex  http://127.0.0.1:8765/ask =====
  [question vide]  statut=200 duree=0.25 s   corps={"ok": false, "error": "question vide"}
  [vraie question] statut=200 duree=5.00 s   ok=true  answer=PONG
===== claude http://127.0.0.1:8766/ask =====
  [question vide]  statut=200 duree=0.39 s   corps={"ok": false, "error": "question vide"}
  [vraie question] statut=200 duree=2.32 s   ok=true  answer=PONG
```

Le verdict n'est donc **jamais** dans le statut : il est dans `ok` et `answer`.
Une sonde qui ne lit que le statut est structurellement incapable d'être
honnête — elle dira « vert » à un pont dont le harnais est déconnecté, absent,
ou en panne. C'était exactement le scénario du brief : l'utilisateur configure,
voit vert, et la panne apparaît en démonstration.

À noter au passage : un vrai PONG Codex prend **5,00 s**, donc *juste* au-dessus
de l'ancien délai de cinq secondes. L'ancien commentaire
« un PONG reel depasse 5 s » était exact ; la borne de 5 s aurait produit un faux
négatif systématique dès qu'on aurait posé une vraie question.

---

## 3. Ce qui a été corrigé

### 3.1 Une vraie question minimale, à réponse vérifiable

```python
QUESTION_SONDE = "Reponds par un seul mot : PONG. N'ajoute aucun autre mot."
MARQUEUR_SONDE = "pong"
```

Le mot attendu est **dans** la question, donc la vérification ne dépend pas
d'une devinette. Les ponts font précéder la question de leur propre consigne de
forme (« deux ou trois phrases parlables ») ; les deux harnais ont malgré tout
répondu exactement `PONG`. La casse n'est pas pertinente (`PONG`, `pong`,
`Pong.`, `Le mot demande est PONG.` passent tous), une réponse à côté ne passe
pas.

### 3.2 Deux temps pour les harnais

1. **Question vide, bornée à 5 s** — ne lance pas le harnais. Distingue
   « rien n'écoute », « le jeton est refusé », « ce n'est pas le pont », et
   « le pont est là ». Sert aussi à échouer vite.
2. **Vraie question, bornée à 100 s** — seul ce temps peut allumer le vert.

`DELAI_HARNAIS_S = 100.0` est choisi **au-dessus** des bornes propres des ponts
(40 s pour `codexbridge`, 90 s pour `clibridge`, `DEFAULT_TIMEOUT_S`). Un test
importe ces deux constantes et vérifie l'inégalité, pour que la relation ne
dérive pas en silence : si le client abandonnait avant le pont, un pont qui a
répondu serait dit injoignable.

### 3.3 Le corps est vérifié pour les quatre services

| Service | Ce qui est vérifié, au-delà du statut |
|---|---|
| Codex / Claude | `ok is True` **et** `answer` contient le mot attendu |
| Modèle distant | `choices[0].message.content` (ou `choices[0].text`) non vide |
| JeV | `answers` contient `phrase_finished`, le seul signal posé |

Un corps illisible (du HTML rendu avec un statut de succès) n'est jamais une
réponse : `_corps()` rend `None` et la sonde dit « muet ».

### 3.4 Quatre états, portés par la sonde

`Sonde` reçoit un champ `etat`. Un appel ancien à quatre arguments continue de
fonctionner : `__post_init__` déduit l'état le **plus prudent** (`repond` si
`ok`, sinon `injoignable`) — jamais l'inverse.

### 3.5 `outil_cli_pret` ne se contente plus de l'exécutable

Le brief avait raison : `shutil.which` prouve l'installation, pas l'abonnement.
La sonde vérifie maintenant **aussi** la trace locale que laisse l'outil
officiel après une connexion :

- Codex : `~/.codex/auth.json` avec `OPENAI_API_KEY` non vide **ou** `tokens` non vide ;
- Claude : `~/.claude/.credentials.json` non vide, **ou** `oauthAccount` dans `~/.claude.json`
  (sur Windows les identifiants vivent dans le gestionnaire d'informations
  d'identification, donc le seul fichier `.credentials.json` aurait produit un
  faux négatif).

Trois issues : pas installé → `injoignable` ; installé sans connexion →
**`muet`, pas vert** ; installé avec connexion → vert. Un fichier présent mais
illisible rend `None`, donc « installé, connexion illisible » et **pas vert** :
quand on ne sait pas, on ne dit pas oui.

Rien n'est envoyé sur le réseau, aucun jeton OAuth n'est interrogé (ce qui
resterait contraire aux conditions des outils), et **aucune valeur** n'est lue
au-delà de sa présence : un test écrit un faux secret dans le fichier
d'identifiants et vérifie qu'il n'apparaît ni dans le libellé ni dans les
journaux. Le libellé dit lui-même sa limite : « Cela ne prouve pas encore
l'abonnement : seul un appel au pont Codex le prouve. »

### 3.6 Libellés : trois phrases distinctes, aucune ambiguïté

Les trois états du brief donnent trois phrases différentes (un test construit les
trois cas et vérifie que l'ensemble des libellés a bien trois éléments) :

- **joignable et répond** → « Codex a repondu a la question de test. »
- **joignable mais ne répond pas** → « Le pont Codex est joignable, mais Codex
  n'a pas donne la reponse attendue. » (et cinq variantes selon la raison :
  jeton refusé, délai dépassé, harnais introuvable, harnais en échec, réponse
  inexploitable)
- **injoignable** → « Le pont Codex ne repond pas : rien n'a repondu. »

Plus un quatrième, « absent », pour une clé non posée : il n'y a alors rien à
tester.

Le texte brut du pont n'est **jamais** recopié à l'écran (il peut citer un
chemin, un code de sortie, une ligne de la sortie du harnais). `_dicible()` le
vérifie sur chaque libellé : pas d'accolade, pas de `Traceback`, pas d'adresse,
pas de `HTTP`, pas de code de statut.

---

## 4. Ce que chaque voyant prouve désormais

C'est la question posée par le brief. Réponse complète, voyant par voyant.

| Bloc de l'écran | Vert (`repond`) prouve | Ne prouve PAS | Orange (`muet`) | Rouge |
|---|---|---|---|---|
| **Pont Codex** | le pont écoute à cette adresse, ce jeton est accepté, **et Codex a rendu le mot attendu** — mesuré 5,00 s le 21/09 | que Codex saura traiter une vraie demande ; que le dépôt est bien celui attendu | pont joignable mais : jeton refusé / délai dépassé / `codex introuvable` sur l'hôte / échec du harnais / réponse sans le mot attendu | rien n'a répondu dans les 5 s, ou la clé n'est pas posée |
| **Pont Claude** | idem, via le pont CLI avec `agent=claude` — mesuré 2,32 s | idem | idem, plus `agent inconnu` | idem |
| **Codex (outil installé)** | `codex` est dans le PATH **et** une connexion est posée sur cette machine | que l'abonnement est encore valable ; que le harnais répond — c'est le rôle du bloc « Pont Codex » | installé, mais aucune connexion trouvée, ou illisible | `codex` absent du PATH |
| **Claude (outil installé)** | idem | idem | idem | idem |
| **Modèle distant** | l'adresse répond, cette clé est acceptée, **et une complétion avec du contenu est revenue** | que le modèle est celui demandé ; que le contexte tient | clé refusée, ou réponse sans contenu exploitable | rien n'a répondu |
| **JeV** | l'adresse répond, cette clé est acceptée, **et le signal `phrase_finished` est revenu** | que les autres signaux fonctionnent ; que le modèle choisi est le bon | clé refusée, ou `answers` sans le signal posé | rien n'a répondu |
| **Voix / accent** | (pas de voyant) le menu vient du serveur Magpie ; sinon la ligne « Liste de repli » le dit | que la synthèse fonctionnera | — | — |
| **Langue** | (pas de voyant) | — | — | — |

Ce que le vert ne prouvait **avant** cette nuit, pour comparaison : « quelque
chose a répondu avec un statut 200 ». Pour les harnais, cela incluait le cas
`{"ok": false, "error": "question vide"}` revenu en 250 ms — c'est-à-dire
précisément le cas où le harnais n'a jamais été lancé.

### À l'écran

Trois couleurs, et une légende qui les nomme (sinon l'orange se devine) :

```
Vert : le service a répondu à la question de test.
Orange : joignable, mais aucune réponse vérifiable.
Rouge : injoignable, ou rien n'est encore configuré.
```

`PASTILLE_MUET = "#d9a441"`, mesuré rendu à l'écran à côté de `#3dba7a` (vert)
et `#d04a4a` (rouge).

L'aide du pied de page promettait « un délai de cinq secondes » : c'était vrai
tant que les sondes ne posaient aucune question, c'est devenu faux. Elle est
remplacée par un texte dont **le chiffre vient de la constante**, pas d'une
phrase recopiée :

```
Vérifier appelle réellement le service : cinq secondes pour un service distant,
jusqu'à 100 secondes pour un harnais, qui doit vraiment répondre à une question.
```

Un test importe `DELAI_HARNAIS_S` et vérifie que sa valeur apparaît à l'écran :
le libellé ne peut plus dériver du code. (`DELAI_S == 5.0` est vérifié par un
test, puisque « cinq secondes » reste écrit en toutes lettres.)

---

## 5. Bout en bout : ce que j'ai réellement vu fonctionner

Le brief demande de tester pour de vrai. Trois bancs, écrits hors dépôt, lancés
sur le **Python hôte** (3.13.14, Tk 8.6) parce que le conteneur n'a pas
`tkinter` — voir §9.2. Rien n'a été installé sur l'hôte.

### 5.1 Contre les vrais ponts, avec les vrais jetons

Deux aller-retours réels, un seul harnais à la fois, question minimale :

```
 sonder_codex  -> ok=True  etat=repond  latence=11484 ms
   detail=Codex a repondu a la question de test.
 sonder_claude -> ok=True  etat=repond  latence=7438 ms
   detail=Claude a repondu a la question de test.

  outil_cli_pret('codex')  ok=True  etat=repond  latence=1 ms
  outil_cli_pret('claude') ok=True  etat=repond  latence=3 ms
```

Latence 11,5 s = 5 s perdues sur `host.docker.internal` (voir §9.6) + 6,5 s de
vrai aller-retour Codex. C'est le voyant vert qui prouve quelque chose : avant
cette nuit, le même écran affichait vert en 13 ms sans avoir lancé Codex.

Sonde JeV réelle avec une clé volontairement fausse :

```
INFO:httpx:HTTP Request: POST https://api.typesafe.ai/v1/systemone "HTTP/1.1 401 Unauthorized"
INFO:src.onboarding.sondes:sonde jev: etat=muet raison=refuse (cle_len=10, latence_ms=972)
  detail='JeV est joignable, mais il refuse cette cle.'
```

C'est le comportement honnête attendu : joignable, pas utilisable, et la phrase
dit laquelle des deux propositions est vraie.

### 5.2 Fenêtre réellement affichée, géométrie mesurée

Pas une fenêtre retirée : `deiconify()` + `lift()` + 20 passes d'`update()`.

```
fenetre : mapped=1 visible=1
  geometrie demandee : 520x760      geometrie obtenue : 520x760 en (60,105)
  titre : 'Réglages'
  champ BRAIN_MODEL      445x46 px mapped=1
  champ BRAIN_API_KEY    445x46 px mapped=1
  champ CODEX_BRIDGE_URL 445x46 px mapped=1
  pastille codex/claude/jev/brain_distant : 14x14 px, items=1
  bouton Tout verifier : 243x33 px  texte='Tout vérifier'
  saisie vue a l'ecran : 'modele-demontre'
  apres fermer : vivante=False apres=None
```

### 5.3 Saisir, voir, sauvegarder, relire après redémarrage

```
valeur relue a l'ouverture : 'modele-avant'      invite visible : False
valeur vue apres saisie    : 'modele-apres'
show du champ secret       : '*'                  (masqué dès la première frappe)

fichier apres enregistrement :
   'BRAIN_API_ENDPOINT=http://exemple.invalid/v1/chat/completions\r\n'
   '# un commentaire a preserver\r\n'
   'BRAIN_MODEL=modele-apres\r\n'
   'BRAIN_API_KEY=faux-jeton-wxyz\r\n'
commentaire preserve : True      CRLF preserve : True

-- nouvelle fenetre sur le meme fichier (« redemarrage ») --
relecture BRAIN_MODEL   : 'modele-apres'
libelle cle posee       : 'déjà posée : wxyz'
valeur du champ secret  : '' (invite=True)
le jeton en clair apparait : False      le suffixe apparait : True
```

### 5.4 Lisibilité des champs (le `relief=tk.FLAT` du brief)

Le défaut est **déjà corrigé** dans le code que j'ai reçu, et déjà gardé par
`test_champs_sont_visiblement_editables` (`relief != flat`, fond distinct du
panneau, `highlightthickness >= 2`). Je l'ai mesuré plutôt que supposé, en
calculant le rapport de contraste WCAG :

```
-- contraste normal --   panneau #102028
  bg=#1c3a4a relief=solid bd=2 highlightthickness=2 hb=#6a9aac  Segoe UI 11
  bordure/panneau = 5.42:1     invite(#7a96a4)/champ = 3.84:1
  texte saisi : fg=#d8e4ec  contraste = 9.25:1 -> AA (AAA en fait)
-- contraste élevé --
  bg=#2a5060 relief=solid bd=2 hb=#a8e0f0
  bordure/panneau = 11.58:1    invite(#b8d0dc)/champ = 5.42:1
  texte saisi : fg=#d8e4ec  contraste >= AA
```

Ce qui est mesuré là : **le texte saisi est à 9,25:1**, très au-dessus du seuil
AA de 4,5:1. Le seul élément sous AA est l'**invite** (texte fantôme, 3,84:1 en
mode normal) — c'est volontaire, elle doit s'effacer visuellement, et elle
disparaît à la première frappe. J'ai ajouté un test qui mesure ce contraste
(`test_le_texte_saisi_est_lisible_sur_le_fond_sombre`) pour que la lisibilité ne
redevienne pas une opinion.

### 5.5 Installation neuve, aucune clé

Deux variantes : `.env.local` absent seul, puis `.env.local` **et**
`carte_figee.env` absents.

```
ouverture sans exception : True     (56 ms)
voix courante : ''   combo voix : 'Sofia'   combo accent : 'Aucun accent'
accent naturel : 'fr'               combo langue : 'Français'
repli voix : 'Liste de repli : le serveur vocal ne répond pas.'
« Tout verifier » a rendu la main : True
  brain_distant / codex / claude / jev -> ok=False, « … n'est pas encore posé(e) »
```

Aucun plantage, aucun libellé brut : sur 72 libellés affichés, **0** contient
`reglages.`, `sondes.`, `{` ou `}`. C'est le garde-fou qui compte pour les cinq
nouvelles clés i18n manquantes (§9.5) : le repli français s'affiche, jamais la
clé.

`HA_LANG` absent : `src/i18n.langue()` retombe sur `"fr"` et
`native/presence/onboarding.py:169` filtre déjà toute valeur hors `{fr, en}` —
le `ValueError: langue invalide` cité par le brief ne peut plus se produire.
J'ai cherché d'autres valeurs par défaut manquantes du même genre dans mon
périmètre : `accent_naturel()` attrape `OSError` et rend `"fr"`,
`voix_courante()` rend `""`, `_monter_menu_voix` retombe sur `Sofia`,
`options_accent` ne suppose aucune liste, `libelle_pour_accent` et
`libelle_pour_langue` rendent toujours le premier choix si la valeur est
inconnue. Je n'en ai pas trouvé d'autre qui lève.

### 5.6 « Vérifier » et « Tout vérifier » appellent bien les sondes corrigées

Avec les quatre états injectés, rendu mesuré à l'écran :

```
  brain_distant  ok=True  pastille=#3dba7a  'Le modele distant a repondu.'
  codex          ok=True  pastille=#3dba7a  'Codex a repondu a la question de test.'
  claude         ok=False pastille=#d9a441  'Le pont Claude repond, mais Claude n'a pas repondu.'
  jev            ok=False pastille=#d04a4a  'JeV ne repond pas.'
  outil_codex    ok=False pastille=#d9a441  'Codex est installe, aucune connexion trouvee.'
  outil_claude   ok=False pastille=#d04a4a  "Claude n'est pas installe."
```

Trois couleurs distinctes, et le journal ne cite que la longueur des clés :

```
sonder_tout recoit les cles : [... 11 cles ...]
   BRAIN_API_KEY      = <15 caracteres, masque>
   CODEX_BRIDGE_TOKEN = <15 caracteres, masque>
INFO:native.presence.reglages_ui:reglages sonde codex: ok=True etat=repond
```

---

## 6. Deux défauts trouvés en testant, et corrigés

Ni l'un ni l'autre n'était dans le brief ; les deux sont apparus en faisant ce
que le brief demandait, c'est-à-dire en ouvrant la fenêtre.

### 6.1 « Enregistrer » posait sept clés vides sur une installation neuve

Mesure **avant** correctif : installation vierge, ouverture de la fenêtre, clic
sur « Enregistrer » sans rien saisir →

```
« Enregistrer » sans saisie -> fichier cree : True
  contenu : 'MOUTH_VOICE_NAME=Sofia\nMOUTH_LANGUAGE=fr\nCODEX_BRIDGE_URL=\n
             CLI_BRIDGE_URL=\nBRAIN_MODEL=\nBRAIN_API_ENDPOINT=\nTYPESAFE_MODEL=\n'
```

`.env.local` était créé de toutes pièces avec **cinq clés vides** et deux
valeurs que l'utilisateur n'avait pas choisies (la voix et l'accent par défaut,
recopiés depuis la carte figée). Ce n'est pas cosmétique : `.env.local` est
passé à `docker compose --env-file`, donc une clé vide **écrase** la valeur que
le conteneur ou la carte figée avait posée. Le geste le plus naturel de la
démonstration — ouvrir les réglages, ne rien changer, cliquer Enregistrer —
pouvait casser la configuration.

Correctif : `FenetreReglages` mémorise ce que chaque champ affichait à
l'ouverture (`self._charges`) et `enregistrer()` ne pose que ce qui a changé.
Un champ prérempli que l'utilisateur efface reste une intention explicite et
continue d'être écrit vide. Après correctif :

```
« Enregistrer » sans saisie -> fichier cree : False
```

Quatre tests couvrent les quatre cas (rien changé / une clé ajoutée / une valeur
modifiée / un champ vidé volontairement).

### 6.2 Du bruit Tcl à chaque fermeture de fenêtre

Le tic de la file (`after(40, self._pomper_file)`) est porté par la fenêtre mais
n'était pas annulé à la fermeture. À chaque fermeture, Tk remontait :

```
invalid command name "2260678104320_pomper_file"
    while executing  ("after" script)
```

six fois de suite sur un seul banc. Ce n'est pas un plantage, mais c'est
exactement le genre de trace qui finit dans la console pendant une
démonstration. `fermer()` annule désormais le tic avant de détruire ; le banc ne
remonte plus rien (`invalid command name present : False`) et un test vérifie
que `_apres` repasse à `None`.

---

## 7. Tests

TDD, rouge d'abord. Le rouge a été mesuré **avant** toute modification de
`sondes.py`, dans le conteneur :

```
$ docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest \
      dev/tests/test_onboarding_sondes.py -q -p no:cacheprovider --no-header --tb=no
FFF.......FF.........F...F.F..EEEEEEEEEEEFF.FFFFFFFFFFF............      [100%]
21 failed, 35 passed, 11 errors in 6.78s
```

### 7.1 Commande du brief — sélection

Le brief donne `python -m pytest dev/tests -q -k "onboarding or reglages or sondes"`.
**Cette commande ne peut pas s'exécuter telle quelle dans le conteneur** : elle
est interrompue par une erreur de collecte sans rapport avec mon périmètre
(§9.1). Sorties exactes, avec le seul ajustement nécessaire.

Conteneur `mother-core-dev`, 2026-09-21 01:04 UTC :

```
$ docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest dev/tests -q -rs \
      -p no:cacheprovider --no-header --tb=line -k "onboarding or reglages or sondes" \
      --ignore=dev/tests/test_health_sondes.py
.....................................ss..............sssssFss........... [ 75%]
....sssssssssssssssssssss...ssssss...sssss.sss                           [100%]
=================================== FAILURES ===================================
/workspace/native/presence/overlay.py:18: ModuleNotFoundError: No module named 'tkinter'
=========================== short test summary info ============================
SKIPPED [1] dev/tests/test_indicateur_conversation.py:6: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_connexion_jev.py:6: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_interruption.py:14: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_stop_mains_libres.py:12: could not import 'tkinter': No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_mains_libres.py:113: Tk indisponible : No module named 'tkinter'
SKIPPED [1] dev/tests/test_presence_onboarding.py:27: could not import 'tkinter': No module named 'tkinter'
SKIPPED [7] dev/tests/test_presence_onboarding.py:156: Tk indisponible : No module named 'tkinter'
SKIPPED [35] dev/tests/test_reglages_ui.py:60: Tk indisponible : No module named 'tkinter'
1 failed, 145 passed, 48 skipped, 1404 deselected in 11.72s
```

**Le conteneur n'a pas `tkinter`** : les 35 skips de `test_reglages_ui.py` sont
toute l'interface. Ce run ne valide donc **aucune** ligne de la fenêtre. La
sélection doit aussi être jouée sur l'hôte.

Hôte (Python 3.13.14, Tk 8.6), 2026-09-21 03:05 :

```
$ python -m pytest dev/tests -q -rs -p no:cacheprovider -p no:warnings --no-header --tb=no \
      -k "onboarding or reglages or sondes" --ignore=dev/tests/test_debit.py \
      --ignore=dev/tests/test_piper_taux.py --ignore=dev/tests/test_pocket_transposition.py \
      --ignore=dev/tests/test_qwen3_asr.py --ignore=dev/tests/test_supertonic_tts.py \
      --ignore=dev/tests/test_transposition.py
SKIPPED [1] dev\tests\test_presence_onboarding.py:163: Tk indisponible : invalid command name "tcl_findLibrary"
SKIPPED [1] dev\tests\test_presence_onboarding.py:163: Tk indisponible : Can't find a usable tk.tcl ...
191 passed, 2 skipped, 1389 deselected in 37.47s
```

Les six `--ignore` sont des modules que le Python hôte ne peut pas **importer**
(`scipy`, `torch` absents de l'hôte) : sans eux, la collecte s'interrompt et
rien ne s'exécute. Aucun n'est dans mon périmètre.

Les 2 skips restants sont le flake Tcl de `test_presence_onboarding.py`
(§9.4), hors périmètre. Run précédent de la même commande : `190 passed,
2 skipped` ; run encore avant : `157 passed, 1 failed` **en ligne de base, avant
mes modifications**, le failed étant `test_dessiner_eclair_pose_un_polygone_allume`
sur le même flake. Il est intermittent, il n'est pas à moi, et je ne l'ai pas
masqué.

Interface seule, sur l'hôte :

```
$ python -m pytest dev/tests/test_reglages_ui.py -q -rs -p no:cacheprovider -p no:warnings --no-header
........................................................                 [100%]
56 passed in 23.46s
```

**56 passed, 0 skipped.** À comparer à la ligne de base mesurée en début de nuit
dans les mêmes conditions : `52 passed, 2 skipped` — les deux skips étaient
`test_verifier_desactive_le_bouton_et_rend_la_pastille`, c'est-à-dire le test
qui vérifie précisément que « Vérifier » désactive le bouton et rend la
pastille. Il ne passait jamais (§9.4 explique le correctif).

Sondes seules, dans le conteneur :

```
$ docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest \
      dev/tests/test_onboarding_sondes.py dev/tests/test_onboarding_reglages.py -q \
      -p no:cacheprovider --no-header --tb=short
........................................................................ [ 68%]
.................................                                        [100%]
105 passed in 6.26s
```

### 7.2 Commande du brief — suite complète

Conteneur, 2026-09-21 01:04 UTC :

```
$ docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest dev/tests -q \
      -p no:cacheprovider --no-header --tb=line --ignore=dev/tests/test_health_sondes.py
=========================== short test summary info ============================
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
4 failed, 1520 passed, 72 skipped, 2 xfailed, 41 warnings in 18.09s
```

Les 4 échecs ont **tous** pour cause `ModuleNotFoundError: No module named
'tkinter'`, directement (`overlay.py:18`, `app.py:24`) ou via un
sous-processus (`test_taquet_produit.py:73`, dont l'`AssertionError` porte un
traceback d'import de `native/presence/overlay.py`). Vérifié test par test. Ce
sont des artefacts du conteneur, pas des régressions : aucun des quatre fichiers
n'est dans mon périmètre, et la ligne de base du dépôt en comptait déjà 4 de la
même cause.

Hôte, 2026-09-21 03:07 :

```
$ python -m pytest dev/tests -q -p no:cacheprovider -p no:warnings --no-header --tb=no -rf \
      --ignore=<les six modules scipy/torch>
78 failed, 1502 passed, 2 xfailed in 52.18s
```

Les 78 échecs hôte sont des artefacts d'environnement, répartis ainsi :

| Fichier | Nb | Cause |
|---|---|---|
| `test_outils_voix.py` | 19 | `async def` non supporté : pas de `pytest-asyncio`/`anyio` sur l'hôte |
| `test_hostagent_transport.py` | 11 | `No module named 'fastapi.testclient'; 'fastapi' is not a package` |
| `test_warmup.py` | 10 | `async def` non supporté |
| `test_presence.py` | 9 | `async def` non supporté |
| `test_resample_continu.py` | 8 | `No module named 'soxr'` |
| `test_integration.py` | 6 | `async def` non supporté |
| `test_hostagent_rapport.py` | 5 | `fastapi.testclient` |
| `test_mouth_magpie.py` | 4 | `No module named 'scipy'` |
| `test_stepfun.py` | 3 | `async def` non supporté |
| `test_tours_serialises.py` | 1 | `async def` non supporté |
| `test_raccourcis_windows.py` | 2 | **échecs de contenu réels**, voir §9.3 |

**Aucun** n'est dans `test_onboarding_sondes.py`, `test_onboarding_reglages.py`,
`test_reglages_ui.py` ni `test_presence_onboarding.py` (vérifié en filtrant la
liste des `FAILED` sur ces quatre noms : zéro ligne).

Le Python hôte n'est pas un environnement de test viable pour cette suite : il
lui manque `pytest-asyncio`, `scipy`, `soxr`, et son `fastapi` est cassé. Il ne
sert ici qu'à une chose — exécuter Tk, que le conteneur n'a pas.

### 7.3 Ce que les tests ajoutés couvrent

**Sondes** (24 nouveaux ou réécrits) : les quatre états et leur distinction ;
`{"ok": false}` avec statut 200 ne passe plus en vert (le défaut du brief, en
test de régression) ; `{"ok": true, "answer": ""}` non plus ; une réponse à côté
non plus ; insensibilité à la casse ; la question posée est bien
`QUESTION_SONDE` ; aucun champ inventé n'est envoyé aux ponts ; la borne client
dépasse les bornes des deux ponts (constantes importées depuis les ponts) ; un
harnais qui pend est borné ; `delai depasse`, `introuvable`, `agent inconnu`,
échec du harnais et statut inattendu au second temps donnent chacun la bonne
raison ; corps illisible ; modèle distant sans contenu ; JeV sans le signal
posé ; jeton absent = aucun appel ; garde-fou de contrat contre
`native/codexbridge` et `native/clibridge` eux-mêmes ; `outil_cli_pret` dans ses
quatre issues (absent / installé sans connexion / installé connecté /
identifiants illisibles), sans jamais révéler le contenu des identifiants.

**Interface** (12 nouveaux) : trois couleurs distinctes pour trois états ;
harnais joignable-et-muet ≠ vert ; sonde à quatre arguments sans état ne devient
pas complaisante ; légende affichée ; aide annonçant le délai réel ; fermeture
annulant le tic ; les quatre cas d'« Enregistrer » ; contraste WCAG du texte
saisi mesuré dans les deux modes.

**Tests existants réécrits** (et pourquoi) : `test_sonde_a_les_champs_imposes`
(le champ `etat` s'ajoute) ; `test_codex_poste_la_question_avec_le_jeton` et
`test_claude_poste_l_agent_sur_le_pont_cli` (deux appels désormais, et la
dernière question n'est plus vide) ; `test_reponse_ok_pose_la_latence_et_le_service`,
`test_sonder_tout_*`, `test_pont_retente_*`,
`test_pont_reussi_du_premier_coup_*` (le double doit porter une vraie réponse
vérifiable) ; les six `test_outil_cli_pret_*` (la présence de l'exécutable ne
suffit plus). J'ai aussi **supprimé** un test que j'avais écrit sur une prémisse
fausse — voir §9.7.

---

## 8. Secrets

Rien de ce que j'affiche ne révèle une clé.

- À l'écran : les quatre champs secrets sont en `show="*"` dès la première
  frappe ; une clé déjà posée n'apparaît que par ses quatre derniers caractères
  (`déjà posée : wxyz`) ; après « Enregistrer », le champ est vidé et l'invite
  revenue. Vérifié en parcourant tous les libellés de la fenêtre : le jeton
  complet n'y figure pas, le suffixe si.
- Dans les journaux : `sondes.py` ne journalise que `cle_len` (la longueur) et
  l'état. `reglages_ui.py` ne journalise que `ok` et `etat`. Un test met une
  fausse clé en clair, passe `caplog` en DEBUG et vérifie qu'elle n'apparaît ni
  dans les journaux ni dans le libellé ; un second fait pareil avec le contenu
  d'un fichier d'identifiants Codex.
- Dans ce rapport : aucune valeur. Les seules longueurs citées (64 et 40
  caractères) viennent du banc, qui masquait déjà la valeur.
- `src/onboarding/reglages.py` n'a pas été modifié ; il n'embarque toujours
  aucun logger.

---

## 9. Hors périmètre — sept constats à transmettre

Rien de ce qui suit n'a été modifié par moi. Classé par conséquence sur la
démonstration du 2026-09-25.

### 9.1 La commande de test du brief est inutilisable dans le conteneur

`dev/tests/test_health_sondes.py:17` fait
`from handlers import handle_health_check, handle_vault_note` après avoir ajouté
`workers/night_health_vault_note` à `sys.path`. **`workers/` n'est pas monté
dans `mother-core-dev`** :

```
$ docker inspect mother-core-dev --format "{{range .Mounts}}..."
  logs, models, native, src, .env.local, data, dev     <- pas workers/, pas packaging/
$ docker exec mother-core-dev ls /workspace/workers
ls: cannot access '/workspace/workers': No such file or directory
```

Conséquence : `pytest dev/tests` — avec ou sans `-k` — s'arrête sur
`Interrupted: 1 error during collection` et **rien ne s'exécute**. Toute commande
du brief citée sans `--ignore=dev/tests/test_health_sondes.py` ne peut pas avoir
été jouée dans le conteneur. À corriger côté `docker-compose.yml` (monter
`workers/`) ou côté test (sauter si le module est absent).

Au passage : `nights/` non plus n'est pas monté, mais `/workspace/nights` existe
— c'est une copie **figée dans l'image**. Un agent qui lirait `nights/` depuis le
conteneur lirait une version périmée.

### 9.2 Le vert du conteneur ne couvre aucune interface

48 skips de la sélection et 72 de la suite complète viennent de l'absence de
`tkinter`, dont **les 35 tests de `test_reglages_ui.py`**. Le conteneur ne peut
pas valider la surface que le jury verra. Tout ce qui touche Tk doit être joué
sur l'hôte — ce que j'ai fait, et ce que ce rapport chiffre séparément.

### 9.3 Deux échecs de contenu réels, visibles seulement sur l'hôte

`dev/tests/test_raccourcis_windows.py` échoue **pour de vrai** sur l'hôte (le
conteneur le saute, `packaging/` n'étant pas monté) :

```
test_raccourcis_windows.py:54:  assert 'hyper-ambient.bat' in "<contenu du script d'installation>"
test_raccourcis_windows.py:109: AssertionError: assert 87 <= 10
```

Le second compare le nombre de lignes d'un fichier d'installation Windows (87) à
une borne de 10. C'est le couloir `packaging/` + `README.md`, explicitement hors
de mon périmètre cette nuit — mais ce sont les deux seuls échecs de contenu que
j'aie vus, et ils portent sur le chemin du double-clic de la soutenance.

### 9.4 Le helper Tk de `test_presence_onboarding.py` saute un test à chaque run

`_ouvrir_tk()` (ligne 152) crée une racine Tk, la détruit, puis le test en crée
une seconde. Sur Windows, **la toute première initialisation de Tcl dans le
processus pytest échoue** (`Can't find a usable init.tcl`, ou `tk.tcl`, ou
`tcl_findLibrary`, ou `ttk/combobox.tcl` selon le run) puis réussit. Le helper
abandonne au premier essai et transforme l'incident en `pytest.skip`.

Mesuré sur cette nuit, quatre runs de la sélection hôte : 1 failed, puis
0 failed/2 skipped, puis 2 skipped, puis 1 failed — jamais stable.

J'ai corrigé exactement cela dans **mon** fichier (`test_reglages_ui.py`) en
réessayant trois fois avant de sauter : les 2 skips permanents ont disparu et
`test_verifier_desactive_le_bouton_et_rend_la_pastille` — le test qui vérifie
que « Vérifier » désactive le bouton et rend la pastille — s'exécute enfin. Le
même correctif dans `test_presence_onboarding.py` ferait passer
`test_dessiner_eclair_pose_un_polygone_allume` et les 7 tests sautés en ligne 156.
**Je ne l'ai pas appliqué** : ce fichier teste `native/presence/onboarding.py`,
qui n'est pas dans mon périmètre. Le correctif est 4 lignes, il est dans
`test_reglages_ui.py:57-76` si quelqu'un veut le recopier.

### 9.5 Cinq clés i18n manquent, donc l'anglais retombe sur le français

`src/i18n/__init__.py` est hors périmètre (et un autre agent l'a réécrit pendant
la nuit : 920 lignes à ma première lecture, 940 ensuite). J'ai donc écrit les
nouveaux libellés avec un repli français local, via un helper `_libelle()` qui
essaie `t(cle)` et retombe sur la phrase en français si la clé est absente.
Vérifié sous `HA_LANG=en` : aucune clé brute ne s'affiche, les cinq phrases
sortent en français.

Clés à ajouter dans `src/i18n/__init__.py` (table `_FR` **et** `_EN`) pour
retrouver la parité anglaise :

| Clé | Français actuellement affiché par repli |
|---|---|
| `sondes.outil_connecte` | L'outil {nom} est installé, et une connexion {nom} est posée sur cette machine. Cela ne prouve pas encore l'abonnement : seul un appel au pont {nom} le prouve. |
| `sondes.outil_sans_connexion` | L'outil {nom} est installé, mais aucune connexion {nom} n'est posée sur cette machine. Dans PowerShell : {commande} |
| `sondes.outil_connexion_illisible` | L'outil {nom} est installé, mais sa connexion n'a pas pu être lue. Dans PowerShell : {commande} |
| `reglages.verifier_aide_delais` | Vérifier appelle réellement le service : cinq secondes pour un service distant, jusqu'à 100 secondes pour un harnais… |
| `reglages.legende_etats` | Vert : le service a répondu à la question de test. Orange : joignable, mais aucune réponse vérifiable. Rouge : injoignable… |

⚠ Les libellés des **quatre états HTTP** (`_TEXTES` dans `sondes.py`) sont en
français dans le code, comme l'étaient déjà `_ABSENT`/`_INJOIGNABLE`/`_REFUSE`/
`_OK` avant moi. Je n'ai pas changé cette convention ; la traduire suppose de
déplacer tout le catalogue dans `src/i18n`, ce qui n'est pas mon périmètre.

Deux clés deviennent orphelines : `reglages.verifier_aide` (remplacée par
`reglages.verifier_aide_delais`, et son texte « cinq secondes » était devenu
faux) et `sondes.outil_present` (remplacée par les trois clés ci-dessus).
`test_reglages_ui.py:374` teste encore la traduction anglaise de
`reglages.verifier_aide` : il passe, mais il teste une clé que l'interface
n'utilise plus.

### 9.6 Cinq secondes perdues à chaque vérification, depuis l'hôte

`.env.local` pose `CODEX_BRIDGE_URL=http://host.docker.internal:8765/ask`.
Depuis l'hôte, cet hôte **ne répond pas** et tombe au bout du délai :

```
 codex  http://host.docker.internal:8765/ask
  injoignable en 5012 ms : TimeoutError
```

Le repli sur `127.0.0.1` (ajouté par un agent précédent, et que j'ai conservé)
trouve le pont, mais **après** ces cinq secondes. Coût mesuré : 11,5 s pour un
« Vérifier » Codex dont 5 s d'attente inutile, et les quatre sondes de
« Tout vérifier » partant en parallèle, 5 s de délai plancher sur tout
l'écran. Comportement antérieur à mes modifications, que je n'ai pas changé
pour ne pas déstabiliser un repli écrit et testé par un autre cette semaine.

Piste si quelqu'un le prend : le pont répond à la question vide en 250–380 ms,
donc une borne de 1,5 s pour le **premier** temps quand une adresse alterne
existe suffirait, ou mieux, essayer les deux hôtes en parallèle au premier temps
(la question vide ne lance rien et les ponts sont multi-fils).

### 9.7 Le contrat du pont harnais est mal décrit ailleurs que dans le code

J'ai commencé par faire cartographier le pont par un sous-agent, qui m'a rendu
un protocole détaillé et **faux** : handler dans `dev/scripts/serve_hostagent.py`,
réponse `{"ok", "reponse", "duree_ms", "sortie", "erreur"}`, champ `timeout`
modifiable par requête borné à 10..300, file à une place rendant 429, délai
serveur 408. J'ai codé une première version contre ce contrat, puis je l'ai
confronté au pont en marche : la réponse portait `answer`, pas `reponse`, et mes
deux harnais sont revenus « muets » alors qu'ils fonctionnaient.

Vérifié dans le code, la vraie source est ailleurs :

```
$ grep "/ask|add_post|web.post|aiohttp|8765|8766" dev/scripts/serve_hostagent.py
No matches found
```

Le vrai contrat, dans `native/codexbridge/bridge.py` (5 201 o, 11/09 20:12) et
`native/clibridge/bridge.py` (7 538 o, 13/09 13:14) — les deux stables, non
touchés cette nuit :

```
POST /ask   Authorization: Bearer $CODEX_BRIDGE_TOKEN / $CLI_BRIDGE_TOKEN
  requete : {"question": str}                          (codexbridge)
            {"question": str, "agent": "claude"|"hermes"}   (clibridge)
  reponse : {"ok": true,  "answer": "..."}
            {"ok": false, "error": "..."}
  statuts : 200 dans tous les cas de figure ci-dessus ; 401 non autorise ;
            404 chemin inconnu ; 400 requete illisible
  erreurs : question vide | delai depasse | codex introuvable |
            claude introuvable | hermes indisponible | agent inconnu |
            <agent> a echoue (code N)
  borne   : 40 s (codexbridge), 90 s reglable (clibridge) — PAS de champ
            `timeout` dans la requete, il serait ignore
  serveur : ThreadingHTTPServer -> une requete = un fil, PAS de place unique,
            PAS de 429
```

`src/brain/tools_codex.py:104` et `tools_cli.py:152` lisent bien
`payload.get("answer")`, ce qui corrobore. **Si un brief ou une étude de cette
nuit décrit le pont harnais avec `reponse`, un `timeout` côté requête, ou une
file à une place, il est faux** — j'ai moi-même écrit un test sur cette dernière
prémisse avant de la vérifier, et je l'ai supprimé. Un test de garde-fou importe
désormais les deux modules de pont et vérifie que le champ que je lis est bien
celui qu'ils écrivent.

---

## 10. Ce qui n'a pas pu être vérifié

- **L'interface dans le conteneur** : `tkinter` absent, 35 tests sautés. Tout ce
  qui concerne la fenêtre a été joué sur l'hôte uniquement (§5, §7.1).
- **Le scénario « machine vierge » complet** : je n'ai pas réinstallé Docker,
  réservé le GPU ni recréé `.env.local`. J'ai vérifié le maillon dont j'ai la
  charge — fenêtre ouverte sans aucun réglage, sans clé, sans carte figée, sans
  plantage (§5.5) — pas les six étapes manuelles qui le précèdent.
- **Le modèle distant en vert** : `BRAIN_API_ENDPOINT`/`BRAIN_API_KEY` ne sont
  pas posés sur cette machine et je n'allais pas en inventer. La sonde a été
  vérifiée en « absent » (aucun appel émis) et contre des doubles pour les trois
  autres états. Le vert du modèle distant n'a donc **jamais été observé en vrai**.
- **JeV en vert** : vérifié en vrai seulement côté refus (401 avec une clé
  fausse, §5.1). Le vert repose sur des doubles ; la clé réelle n'a pas été
  utilisée, pour ne pas consommer d'appel sur un compte tiers sans nécessité.
- **Les chemins d'erreur des ponts** (`delai depasse`, `introuvable`,
  `a echoue (code N)`) : couverts par des doubles fidèles au contrat relevé dans
  `native/codexbridge/bridge.py` et `native/clibridge/bridge.py`, pas provoqués
  en vrai — il aurait fallu désinstaller `codex` ou laisser tourner un harnais
  40 s.
- **Le rendu visuel** : géométrie, couleurs et contrastes sont mesurés
  numériquement (§5.2, §5.4), pas regardés. Aucune capture d'écran n'a été
  produite.
- **L'installateur et les raccourcis Windows** : `packaging/` interdit et non
  monté. Les deux échecs de contenu de §9.3 sont signalés, pas investigués.
- **La suite complète sur un environnement sain** : ni le conteneur (pas de Tk,
  pas de `workers/`) ni l'hôte (pas de `pytest-asyncio`, `scipy`, `soxr`,
  `fastapi` cassé) ne peuvent exécuter les 1 600 tests. Les deux runs sont
  donnés avec leurs artefacts nommés un par un, aucun échec n'étant dans mon
  périmètre.
- **L'historique git** : aucune commande git exécutée, comme demandé. Le
  périmètre est établi par horodatage (§1), qui est un sur-ensemble des fichiers
  suivis mais ne certifie pas ce qui est versionné.

---

## 11. Reproduction

```powershell
# sondes + ecriture des reglages (conteneur, reference)
docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest `
  dev/tests/test_onboarding_sondes.py dev/tests/test_onboarding_reglages.py `
  -q -p no:cacheprovider

# interface Tk : hote obligatoire, le conteneur n'a pas tkinter
python -m pytest dev/tests/test_reglages_ui.py -q -rs -p no:cacheprovider

# selection du brief, conteneur puis hote
docker exec -e PYTHONDONTWRITEBYTECODE=1 mother-core-dev python -m pytest dev/tests -q -rs `
  -p no:cacheprovider -k "onboarding or reglages or sondes" `
  --ignore=dev/tests/test_health_sondes.py

python -m pytest dev/tests -q -rs -p no:cacheprovider -k "onboarding or reglages or sondes" `
  --ignore=dev/tests/test_debit.py --ignore=dev/tests/test_piper_taux.py `
  --ignore=dev/tests/test_pocket_transposition.py --ignore=dev/tests/test_qwen3_asr.py `
  --ignore=dev/tests/test_supertonic_tts.py --ignore=dev/tests/test_transposition.py
```

Les bancs de bout en bout (`e2e_reglages.py`, `sonde_reelle.py`, `diag_pont.py`)
sont dans `C:\Users\thoma\AppData\Local\Temp\ha_e2e\`, volontairement hors du
dépôt. `sonde_reelle.py --reel` lance **deux vrais appels de harnais** (Codex
puis Claude, question minimale, `--sandbox read-only` côté pont) : à ne jouer
qu'en sachant cela.
