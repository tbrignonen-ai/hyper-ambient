# Brief — Verification independante avant publication

Bonjour, je suis Opus et je travaille pour Human IA. Merci d'avance.

Deux collegues ecrivent du code en ce moment et personne ne verifie l'ensemble.
C'est ton role. **Tu ne modifies aucun code.** Le depot hyper-ambient passe public
ce soir.

Colle les sorties **exactes** de chaque etape dans ton rapport.

## 1. Suite de tests

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Reference : **1423 passes, 4 echecs pre-existants** (`test_c11_identity`,
`test_presence_onboarding`, deux de `test_taquet_produit`). Nomme tout echec nouveau.

## 2. Sondes reelles des services

Le script existe deja et interroge les quatre services avec les vraies cles :

```
docker exec mother-core-dev python /workspace/dev/scripts/_probe_sondes_reel.py
```

Les quatre doivent ressortir `ok=True` : modele distant, Codex, Claude, JeV.
Rapporte l'etat et la latence de chacun.
**N'affiche jamais une valeur de cle**, seulement sa longueur.

## 3. Installateur, en lecture seule

```
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BGB Training\MOTHER-dev\packaging\windows\installer.ps1" -Diagnostic
```

Il doit finir par `Verdict : pret` et un code de sortie 0.

**N'execute jamais ce script sans `-Diagnostic`.** Il installerait des composants sur
la machine du fondateur, qui porte aussi un entrainement de modele en cours.

## 4. Parite francais / anglais

Verifie que chaque libelle existe dans les deux langues et qu'aucun ne retombe sur sa
cle brute. Ecris toi-meme un petit script Python jetable dans `/tmp` du conteneur pour
le faire : recupere les cles de `src/i18n/__init__.py`, puis pour `HA_LANG=fr` et
`HA_LANG=en`, recharge `src.i18n` et liste les cles pour lesquelles `t(cle)` rend la
cle elle-meme. Attendu : aucune, dans les deux langues.

## 5. Secrets avant publication

Verifie qu'aucune valeur de cle reelle de `.env.local` n'apparait dans un fichier suivi
par git. Compare les valeurs aux fichiers rendus par `git ls-files`.
N'affiche **aucune valeur** : seulement le verdict et, en cas de fuite, le nom du
fichier et celui de la variable.

## Regles

- Tu ne modifies **aucun** fichier de code.
- Tu n'installes **rien**, et tu ne touches pas au Python de l'hote.
- Tu n'executes **aucune** commande git.
- Ton seul fichier en ecriture est ton rapport.

## Verdict

Termine par un verdict global en trois lignes : ce qui est bon, ce qui est casse, ce
qui est douteux. Sois severe — un doute signale vaut mieux qu'un probleme decouvert
apres publication.

Rapport dans `nights/2026-09-20-OUT-QWEN-VERIFICATION.md`.
