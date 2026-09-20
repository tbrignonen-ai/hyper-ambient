---
date: 2026-09-20
heure: ~20h45 Europe/Paris
type: out
lane: INDICATEUR-CONVERSATION
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-INDICATEUR-CONVERSATION]]"]
---

# OUT — indicateur visuel d'état de conversation

Périmètre respecté : `dev/scripts/serve_hostagent.py` (émission), `native/presence/app.py` (réception + affichage), `src/i18n/__init__.py` (libellés), `dev/tests/test_indicateur_conversation.py` (créé). Presence non lancée. Pas de commande git. Fichiers interdits non touchés (`src/ears/*`, `src/mouth/*`, `native/hostagent/*`, `.env.local`).

## Diff résumé

`dev/scripts/serve_hostagent.py`
- `{"type":"conversation","ouverte":bool,"restant_s":float}` sur le WebSocket existant.
- Émission à chaque ouverture (`engager` → `_ouvrir_conversation`), à la fermeture (mains libres OFF / expiration), et une fois par seconde tant que la fenêtre est ouverte (décompte vivant).
- `restant_s` lu sur `FenetreConversation` sans modifier `src/ears/*`.

`native/presence/app.py`
- `relayer_conversation` dans `consommer_reponse` et l'idle mains libres (`_aspirer_jev_pret` aussi hors `jev_pret`).
- Pastille + texte court sous l'indice mains libres. Palette `ecoute` si conversation ouverte, `repos` sinon ; `palette_pour(..., contraste)`.
- Mains libres OFF : rien (cadre masqué). Fermeture → invitation toute seule.

`src/i18n/__init__.py`
- `ui.conversation_open` / `ui.conversation_invite` dans `ui_presence()` :
  - FR « En conversation — {n} s » / « Dis mon nom pour me parler »
  - EN « In conversation — {n} s » / « Say my name to talk to me »
  - ES overlay (hors `_TABLES`, `langue()` inchangé) : « En conversación — {n} s » / « Di mi nombre para hablarme »

`dev/tests/test_indicateur_conversation.py` (créé)
- Harnais `_application` : ouverte=true → libellé + 24 ; false → invitation ; ML OFF → aucun des deux ; décompte 24 puis 7.

## Pytest (hôte Windows, tel quel)

```
$ python -m pytest -q dev/tests/test_indicateur_conversation.py dev/tests/test_presence_connexion_jev.py dev/tests/test_presence_stop_mains_libres.py
.....................                                                    [100%]
21 passed in 1.79s
```

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_hostagent_transport.py dev/tests/test_fenetre_conversation.py"
.............                                                            [100%]
13 passed, 21 warnings in 0.49s
```

Warnings préexistantes Starlette/anyio, hors périmètre.

## Difficultés

- `FenetreConversation` n'expose pas `restant_s` ; lecture de `_jusqu_a` côté host-agent pour ne pas toucher `src/ears/*`.
- Table UI `es` volontairement hors `_TABLES` (xfail strict `test_parite_anglaise`) ; overlay `_ES` limité aux deux nouvelles clés, `langue()` reste fr/en.
- Idle WS : après `jev_pret`, Presence ne lisait plus le socket hors tour. `_aspirer_jev_pret` tourne aussi à 30 ms en boucle continue, sinon le décompte 1 Hz n'arriverait jamais.
