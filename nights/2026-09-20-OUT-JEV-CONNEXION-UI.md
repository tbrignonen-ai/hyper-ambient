---
date: 2026-09-20
heure: ~18:00 Europe/Paris
type: out
lane: JEV-CONNEXION-UI
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-JEV-CONNEXION-UI]]"]
---

# OUT — UI « Connexion… » à l'activation du mains libres

Périmètre respecté : `native/presence/app.py` + `dev/tests/test_presence_connexion_jev.py`.
Presence non lancée. Pas de commit. Fichiers interdits non touchés.

## Diff résumé

`native/presence/app.py`
- `_basculer_mains_libres()` ON : statut immédiat `hands_free_connecting` (« Connexion… »). Bouton Parler inchangé (non bloqué).
- Réception WS `{"type":"jev_pret"}` : `relayer_jev_pret` dans `consommer_reponse` + idle `_aspirer_jev_pret` après options ON. UI : `hands_free_connected` (« Mains libres prêtes. ») seulement si le statut est encore « Connexion… ».
- Repli 3 s (`racine.after(3000)`) si le message n'arrive pas. Annulé à OFF, à `jev_pret`, et à `fermer()`.
- OFF : hint mains libres ; ni « Connexion… » ni « Mains libres prêtes. ».

`dev/tests/test_presence_connexion_jev.py` (créé)
- ON → « Connexion… », bouton Parler non disabled
- `{"type":"jev_pret"}` → « Mains libres prêtes. »
- OFF → les deux libellés absents

## Pytest (hôte Windows, tel quel)

```
$ python -m pytest -q dev/tests/test_presence_connexion_jev.py dev/tests/test_presence_stop_mains_libres.py dev/tests/test_presence_mains_libres.py
..........................                                               [100%]
26 passed in 1.70s
```

## Difficultés

- Premier rouge : `relayer_jev_pret` importé avant d'exister → erreur de collecte. Tests réécrits sur `_traiter` / `relayer_jev_pret` une fois le symbole en place.
- Tk Windows : second `Tk()` parfois « Can't find a usable init.tcl » si `after(3000)` n'est pas annulé avant `destroy()`. Les tests appellent `_annuler_repli_jev_pret()` dans le finally.
- Repli 3 s non couvert par un sleep dans les tests (budget) : le callback `_repli_jev_pret` est le même chemin d'affichage que `jev_pret`.
