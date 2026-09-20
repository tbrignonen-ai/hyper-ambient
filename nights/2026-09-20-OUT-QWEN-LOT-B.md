---
date: 2026-09-20
heure: ~21:25 Europe/Paris
type: out
lane: ONBOARDING-V2 LOT B
auteur: Qwen
related: ["[[2026-09-20-SPEC-ONBOARDING-V2]]", "[[2026-09-20-OUT-CURSOR-LOT-A]]"]
---

# OUT — Lot B, l'ecriture de la configuration

Perimetre respecte : `src/onboarding/reglages.py` et
`dev/tests/test_onboarding_reglages.py`, rien d'autre. `src/onboarding/__init__.py`
laisse au lot A. Aucune commande git.

Le `.env.local` reel du fondateur n'a ete **ni lu ni ecrit** : horodatage
21:02:48 avant et apres mes runs (21:16 - 21:22), et il est monte `:ro` dans le
conteneur. Chaque test travaille sur un `tmp_path`, et un garde-fou `autouse`
compare l'horodatage du fichier du depot avant/apres chaque test. Les valeurs de
cle des tests sont des faux.

## API

Les quatre signatures imposees, au caractere pres :

```python
def lire_reglages(chemin: Path) -> dict[str, str]: ...
def poser_reglage(chemin: Path, cle: str, valeur: str) -> None: ...
def poser_reglages(chemin: Path, valeurs: dict[str, str]) -> None: ...
def reglage_present(chemin: Path, cle: str) -> bool: ...
```

S'y ajoute une constante `CLES_ONBOARDING`, le tuple des huit noms de variables
de la spec, pour que le lot C ne les reecrive pas a la main.

## Decisions a relire

- **`reglage_present` = valeur non vide.** Une cle absente, une cle vide
  (`BRAIN_API_KEY=`, l'etat d'un `.env.example` recopie) et une cle commentee
  comptent toutes pour « a poser ». **Le lot C en depend** : si Codex attend la
  presence litterale du nom, un ecran croira configuree une cle vide.
- **Sauvegarde en `.env.local.sauvegarde.tmp`, pas `.bak`.** `.gitignore` couvre
  `*.tmp` mais pas `.env.local.bak` : un suffixe `.bak` aurait rendu la
  sauvegarde — donc tous les secrets — versionnable. Un test verrouille les deux
  suffixes.
- **Sauvegarde : une fois par processus et par chemin**, ecrasee a chaque
  session ; c'est l'etat d'avant la session, pas d'avant le dernier ecran. Un
  fichier qui n'existe pas encore n'est pas copie mais reste marque, pour ne pas
  ecraser plus tard le point de retour avec une version que la session vient
  d'ecrire.
- **Cle dupliquee : la derniere occurrence est modifiee**, la premiere laissee
  telle quelle. C'est celle qui gagne pour python-dotenv comme pour
  `docker compose --env-file` ; ecrire la premiere laisserait l'ancienne valeur
  effective.
- **Une ligne commentee n'est jamais reveillee.** Poser une cle dont seule une
  version commentee existe l'ajoute a la fin : le bloc distant de `.env.example`
  reste un choix, pas un effet de bord.
- **Derniere ligne sans saut de ligne final : terminee d'office.** Sans ca la
  cle existante n'etait pas reconnue et la cle nouvelle s'y collait.
- **Guillemets seulement quand le dotenv l'exige.** Nus par defaut : une valeur a
  espaces internes se relit a l'identique, reste lisible par `docker compose
  --env-file` comme par python-dotenv, et un chemin Windows garde ses
  antislashes. Guillemets doubles + echappement pour un espace de bordure, un
  `#` (qui ouvrirait un commentaire en ligne), un saut de ligne (qui injecterait
  une ligne dans le fichier) ou une valeur entamee par un guillemet.
- **Permissions d'origine conservees.** `mkstemp` cree en 0600 : sans ca, un
  service lisant `.env.local` sous un autre utilisateur perdait l'acces apres le
  premier passage de l'onboarding.
- **Refus avant toute ecriture** : nom de variable hors `[A-Za-z0-9_]`
  (`ValueError`) et valeur `None` (`TypeError` — `str(None)` aurait pose
  « None » comme cle API, et l'ecran suivant aurait cru le service configure).
- **Aucune valeur n'est journalisee** : le module n'embarque aucun logger, et les
  exceptions ne citent que des noms de fichiers ou de variables. Un test passe
  `caplog` en DEBUG et verifie que ni l'ancienne ni la nouvelle valeur n'y
  apparaissent.

## Un defaut attrape par les tests

`Path.read_text` applique le mode universel et traduit `\r\n` en `\n`. La
premiere version du module **convertissait donc silencieusement tout
`.env.local` CRLF en LF** — le fichier du fondateur reecrit ligne a ligne, sans
aucune erreur. Corrige : lecture avec `newline=""`. C'est
`test_les_fins_de_ligne_windows_ne_sont_pas_multipliees` qui l'a fait tomber.

## Interfaces avec les autres lots

- **A → B, verifie.** `sonder_tout` lit exactement les huit noms de
  `CLES_ONBOARDING` : `sonder_tout(lire_reglages(chemin))` tient debout sans
  adaptation.
- **B → C.** `poser_reglages` ecrit tout en une fois — une sauvegarde, un
  remplacement atomique — ce qui permet a un ecran de ne rien ecrire tant qu'il
  n'est pas valide, puis de tout poser d'un coup.
- **Couplage a connaitre.** Mon test fait `from src.onboarding import reglages`,
  donc execute le `__init__.py` du lot A. Si cet `__init__` casse, mes 36 tests
  tombent avec. Verifie passe ce soir, leur `__init__.py` etant en place.

## Interop avec python-dotenv

Verifiee a part sur onze valeurs difficiles (espaces de bordure, `#`,
guillemets imbriques, apostrophe, antislashes Windows, accents, valeur vide,
saut de ligne, jeton) : **0 ecart** entre `lire_reglages` et `dotenv_values`,
commentaire et CRLF conserves. Script jetable ecrit dans `dev/out/` (git-ignore)
puis supprime.

## Pytest

Sortie exacte, conteneur :

```
$ docker exec mother-core-dev python -m pytest dev/tests/test_onboarding_reglages.py -q
....................................                                     [100%]
36 passed in 0.21s
```

Hote Windows, meme fichier : `36 passed in 0.44s`. C'est la que Presence
executera le module ; `os.replace` par-dessus un fichier existant et le menage
du temporaire y sont donc couverts pour de vrai.

Suite complete, dernier run (21:27) :

```
$ docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
FAILED dev/tests/test_c11_identity.py::test_cerveau_local_porte_identite_et_style_vocal
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
5 failed, 1388 passed, 32 skipped, 2 xfailed, 39 warnings in 17.09s
```

Les cinq echecs sont les cinq pre-existants de la reference, nom pour nom.
**Aucun echec nouveau.**

Le total bouge pendant la soiree, les autres lots continuant de livrer : mon
premier run donnait `5 failed, 1378 passed, 25 skipped`, soit exactement
1323 (reference) + 19 (lot A) + 36 (lot B) ; le second, cite ci-dessus,
`1388 passed`. Les cinq echecs, eux, n'ont pas change d'un run a l'autre.

## Un risque hors lot, a trancher par Opus

Il existe deja a la racine un `.env.local.sauvegarde-2026-09-20-clibridge`
(21:02:48, pas a moi). `.gitignore` liste `.env.local` au mot pres et `*.tmp` :
ce nom n'est couvert par aucune des deux regles. Je n'ai touche ni `.gitignore`
ni ce fichier.

Aucune valeur de cle dans ce rapport.
