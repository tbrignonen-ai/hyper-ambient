# Specification — L'onboarding que le fondateur a demande

Cette specification fait autorite pour trois chantiers menes en parallele. Chaque
intervenant possede ses fichiers et **ne touche a aucun autre**.

## Ce qui est demande

L'onboarding actuel configure cinq choses cosmetiques (langue, contraste, raccourci,
mains libres, masquage). Le fondateur a demande autre chose, et c'est ce qui manque :

1. **Le modele distant d'escalade** — le declarer et verifier qu'il repond.
2. **Les harnais Codex et Claude Code** — poser leur jeton et verifier qu'ils repondent.
3. **JeV** — poser la cle et verifier que le service repond.
4. Le tout **assiste par le modele local**, pas un formulaire aride.

Aujourd'hui tout cela se configure a la main dans `.env.local`. C'est le sujet.

## Regle absolue sur les secrets

Une cle ne s'affiche jamais en clair, ne s'ecrit jamais dans un journal, ne part jamais
dans un rapport. A l'ecran : un champ masque, et une fois posee, seulement les quatre
derniers caracteres. Dans les traces : la longueur, jamais la valeur. **Aucun rapport ne
doit contenir une valeur de cle, meme partielle, meme pour illustrer.**

## Les trois lots et leurs frontieres

### Lot A — Les sondes (proprietaire : Cursor)

Fichiers possedes : `src/onboarding/__init__.py`, `src/onboarding/sondes.py`,
`dev/tests/test_onboarding_sondes.py`.

Un module qui repond a une seule question par service : **est-ce que ca repond, oui ou
non, et sinon pourquoi en une phrase prononcable ?**

API imposee, a respecter au caractere pres — deux autres lots en dependent :

```python
from dataclasses import dataclass

@dataclass
class Sonde:
    service: str        # "brain_distant" | "codex" | "claude" | "jev"
    ok: bool
    detail: str         # une phrase courte, prononcable, sans jargon ni trace
    latence_ms: float | None

async def sonder_brain_distant(endpoint: str, cle: str, modele: str, client=None) -> Sonde: ...
async def sonder_codex(url: str, jeton: str, client=None) -> Sonde: ...
async def sonder_claude(url: str, jeton: str, client=None) -> Sonde: ...
async def sonder_jev(cle: str, client=None) -> Sonde: ...
async def sonder_tout(reglages: dict, client=None) -> list[Sonde]: ...
```

Exigences :

- **Client HTTP injectable** (`client=None`), comme `src/brain/tools_codex.py` le fait
  deja. Les tests ne doivent toucher aucun reseau.
- **Delai court et borne** : 5 secondes par sonde, jamais plus. Une sonde qui pend est
  pire qu'une sonde qui echoue.
- **Aucune exception ne sort du module.** Tout echec devient un `Sonde(ok=False, ...)`.
- `detail` est destine a etre **lu a voix haute** : « Codex ne repond pas », pas
  « HTTPStatusError 502 ». Jamais d'URL, jamais de trace, jamais de code HTTP.
- Distingue trois causes dans `detail`, parce qu'elles appellent trois gestes differents :
  jeton absent, service injoignable, service qui refuse le jeton.
- Les sondes s'executent **en parallele** dans `sonder_tout`.

Pour les adresses et les formes d'appel, lis `src/brain/tools_codex.py`,
`src/brain/tools_cli.py` et `src/ears/jev_reflexe.py` : les ponts et leurs contrats
existent deja, ne les reinvente pas.

### Lot B — L'ecriture de la configuration (proprietaire : Qwen)

Fichiers possedes : `src/onboarding/reglages.py`, `dev/tests/test_onboarding_reglages.py`.

Ecrire ce que l'utilisateur pose dans `.env.local` **sans rien casser**. Ce fichier
contient deja la configuration de travail du fondateur ; le corrompre lui couterait sa
soiree.

API imposee :

```python
from pathlib import Path

def lire_reglages(chemin: Path) -> dict[str, str]: ...
def poser_reglage(chemin: Path, cle: str, valeur: str) -> None: ...
def poser_reglages(chemin: Path, valeurs: dict[str, str]) -> None: ...
def reglage_present(chemin: Path, cle: str) -> bool: ...
```

Exigences, toutes indispensables :

- **Preserver les commentaires, l'ordre des lignes et les blocs desactives.** Une cle
  existante est modifiee sur place ; une cle nouvelle est ajoutee a la fin.
- **Ecriture atomique** : ecrire dans un fichier temporaire du meme repertoire puis
  remplacer. Une coupure ne doit jamais laisser un `.env.local` tronque.
- **Sauvegarde** de la version precedente avant la premiere ecriture d'une session.
- Gerer les fins de ligne Windows (`\r\n`) sans les multiplier, et l'UTF-8.
- Une valeur contenant des espaces doit se relire a l'identique.
- `lire_reglages` ignore les lignes commentees — une valeur commentee n'est pas une
  valeur.
- **Aucune valeur n'est journalisee.** Jamais.

Noms de variables concernes, tels qu'ils existent deja :
`BRAIN_API_ENDPOINT`, `BRAIN_API_KEY`, `BRAIN_MODEL`, `CODEX_BRIDGE_URL`,
`CODEX_BRIDGE_TOKEN`, `CLI_BRIDGE_URL`, `CLI_BRIDGE_TOKEN`, `TYPESAFE_API_KEY`.

### Lot C — Les ecrans (proprietaire : Codex, lance apres A et B)

Fichiers possedes : `native/presence/onboarding.py`, `dev/tests/test_presence_onboarding.py`,
et les textes dans `src/i18n/__init__.py` (**francais et anglais uniquement**, l'espagnol
est hors perimetre par decision du fondateur).

Trois ecrans nouveaux, apres les ecrans existants, chacun **passable** — « Plus tard » est
toujours offert et n'empeche jamais d'arriver au bout :

1. **Le renfort distant** — adresse, modele, cle. Un bouton « Verifier » qui appelle
   `sonder_brain_distant` et affiche une pastille verte ou rouge avec la phrase du
   `detail`. Explique en une phrase a quoi il sert : les demandes difficiles, quand le
   modele local ne suffit pas.
2. **Les harnais** — Codex et Claude Code sur le meme ecran, une ligne chacun : jeton,
   bouton « Verifier », pastille. Explique en une phrase ce que ca donne : elle peut
   confier du travail aux outils de code deja installes.
3. **JeV** — la cle, « Verifier », pastille. Explique en une phrase que c'est ce qui lui
   permet de savoir quand on s'adresse a elle, et donc ce qui rend le mains libres
   possible.

Exigences :

- **Aucune sonde ne s'execute sur le fil Tk.** Un appel reseau dans le fil de l'interface
  gele la fenetre, et une fenetre qui ne repeint plus passe pour un plantage. Fil separe,
  resultat rendu a Tk par `after()` ou par une file, comme `app.py` le fait deja.
- Pendant une verification : le bouton se desactive et affiche « Je verifie… ». Jamais de
  fenetre figee, jamais de bouton qui ne repond pas.
- Ce qui est pose est ecrit par `poser_reglages` du lot B. Rien n'est ecrit tant que la
  personne n'a pas valide l'ecran.
- **L'assistance par le modele local** : a l'ouverture de chaque ecran, une phrase
  d'explication ecrite d'avance et affichee immediatement. Si le modele local est
  joignable, elle peut etre dite a voix haute par-dessus — mais le texte de repli est
  toujours affiche en premier et ne depend d'aucun service. On ne fait jamais attendre
  devant un ecran vide.
- Au dernier ecran, un **recapitulatif** : chaque service avec sa pastille, et ce qui se
  passera pour ceux qui ne sont pas configures, en une phrase chacun.

## Verification commune

`docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py`

Reference avant ces travaux : **1323 passes, 5 echecs pre-existants**
(`test_c11_identity`, `test_presence_onboarding`, `test_presence_premier_tour`, deux de
`test_taquet_produit`). Aucun echec nouveau n'est accepte.

## Interdits communs

- **Aucune commande git.** Opus relit le diff et commite.
- Ne touche aucun fichier hors de ton lot. Trois intervenants travaillent en meme temps.
- Aucune valeur de cle dans un rapport, un journal, un test ou un message.
