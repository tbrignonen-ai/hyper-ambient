---
date: 2026-09-20
heure: ~19:50 Europe/Paris
type: out
lane: TESTS-ANGLAIS
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-TESTS-ANGLAIS]]"]
---

# OUT — parité anglaise du produit

Périmètre respecté : `dev/tests/test_parite_anglaise.py` (créé). Aucune correction dans `src/i18n/__init__.py` (aucun libellé EN manquant). Fichiers interdits non touchés (`native/*`, `dev/scripts/*`, `src/ears/*`, `src/mouth/*`, `.env.local`). Aucune commande git.

## Inventaire

`ui_presence()` = `ui()` : **56** clés. Tables sources `_FR` / `_EN` : **62** clés chacune (56 `ui.*` + 6 `tools.*`). Jeux identiques. Aucune valeur vide. EN n'est pas un calque FR (sauf `ui.stop` = « Stop » et `ui.feedback_url`, identiques par nature).

`questions_jev()` : **13** identifiants, mêmes chemins imbriqués en `fr` et `en`. EN distinct du FR sur instructions et critères (le champ schéma `type` est partagé : `noul` / `choice` / `score`).

Espagnol **absent** de l'i18n UI et de JeV (voir manques). Secours et réveil ont bien fr / en / es, mêmes clés, phrases distinctes.

## `HA_LANG=en` bascule

| Surface | Bascule |
|---|---|
| `ui_presence()` | oui (`Bienvenue` → `Welcome`, `Parler` → `Talk`) |
| `questions_jev()` | oui (instructions EN, pas un alias FR) |
| `phrase_de_reveil(langue=langue())` | oui (parmi `PHRASES_REVEIL["en"]`) |
| `phrase_de_secours(..., langue=langue())` | oui (phrases `_PHRASES["en"]`) |

Les modules `secours` / `reveil` ne lisent pas `HA_LANG` : il faut passer `langue=`. Côté host-agent (hors périmètre) : `phrase_de_reveil` reçoit `langue_session()` ; les **quatre** appels à `phrase_de_secours` ne passent pas `langue=` → défaut FR même si `HA_LANG=en`. Signalé, non corrigé.

`HA_LANG=es` retombe sur `fr` (`langue()` et `test_c8_i18n`).

## Chaînes FR en dur dans `native/presence/app.py`

Lecture seule, non corrigé. Visibles dans l'UI (statut / erreur) :

| Ligne | Chaîne |
|---|---|
| 211 | `Message illisible.` |
| 216 | `Erreur du transport : {message}` |
| 286 | `Aucune trame de réponse — rien à restituer.` |
| 482 | `Arrêt audio : {exc}` |
| 495 | `Dépendance audio absente : {exc}` |
| 507 | `sounddevice ou websockets absent sur l'hôte.` |
| 525 | `Périphérique audio indisponible. Vérifiez le micro.` |
| 544–545 | `Poignée de main refusée. Le serveur tourne-t-il sur le port 8001 ?` |
| 572 | `Impossible de joindre {url} : {exc}` |
| 1689–1691 | `Clavier : Tab parcours · Entrée active · … parler · Ctrl+H masquer · F6 focus Parler · Échap Stop si parole, sinon quitter` |
| 1991 | repli `Erreur.` |

CLI `--help` (argparse) : description et `help=` entièrement en français (2098–2135). Radios langue : `("fr", "Français"), ("en", "English")` — pas d'espagnol.

Le reste de l'UI passe par `ui_presence()`.

## Manques (signalés, non corrigés)

1. **Pas de table UI `es`** dans `_TABLES`. `ui_presence()` sous `HA_LANG=es` parle français.
2. **Pas de `QUESTIONS_ES`** : `questions_jev("es")` **est** `questions_jev("fr")` (même objet).
3. **`langue()` ignore `es`** (contrat C8 : seul `en` / `en-US` bascule).
4. **Host-agent** : `phrase_de_secours` sans `langue=` → secours vocal reste FR sous `HA_LANG=en`.
5. **Presence** : ~11 statuts/erreurs + aide clavier + argparse encore en français dur.

Parité **anglaise** des catalogues i18n / JeV : tenue. Parité **espagnole** produit (README / `src/core/api.py` annoncent trois langues) : non.

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_parite_anglaise.py dev/tests/test_c8_i18n.py"
.x......x......................                                          [100%]
29 passed, 2 xfailed in 0.19s
```

Les 2 xfail `strict=True` sont l'inventaire machine des trous es (table UI absente ; JeV es = FR). Ils XPASS le jour où quelqu'un ajoute l'espagnol.
