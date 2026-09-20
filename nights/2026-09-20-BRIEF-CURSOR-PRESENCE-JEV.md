# BRIEF Cursor — Presence Mains libres (JeV) + onboarding — 20 sept 15:23
Complexité: complex → close NOTIFY=OG
URGENCE: rendu BGB DEMAIN. Thomas veut voir le bouton avant retest.

## Contexte
- JeV est DÉJÀ branché côté host-agent (JevReflexe, ignore si pas adressé à MOTHER). Toujours actif, pas de toggle UI.
- Presence : texte onboarding `hands_free` seulement, **pas de bouton**. Config actuelle `%LOCALAPPDATA%\hyper-ambient\presence.json` : onboarding_termine, raccourci, langue, contraste.
- Fix mémoire outils DÉJÀ livré (ne pas retoucher sauf conflit).

## Objectif
1. **Bouton « Mains libres »** visible dans l'UI principale Presence (à côté Masquer / Feedback), état ON/OFF clair, focus clavier (takefocus + focus visible).
2. **Config** `mains_libres: bool` dans `ConfigurationPresence` / presence.json (défaut False pour ne pas changer le comportement PTT actuel).
3. **Host-agent** : n'appliquer JeV que si `mains_libres` est actif pour la session (sinon comportement bouton actuel = toujours répondre). Propager le flag via le hello Presence → hostagent (ou champ sur invoke). Si hello n'existe pas encore pour options, ajouter un message `{"type":"options","mains_libres":true}` ou étendre hello existant — regarder le contrat WS.
4. **Onboarding** : ajouter une étape (ou enrichir l'étape 1) qui explique Mains libres / JeV et propose Activer / Plus tard. Ne pas forcer ON. Thomas rejouera l'onboarding après (`--onboarding` existe déjà).
5. i18n FR/EN : labels bouton + étape (réutiliser `ui.hands_free` + nouveaux `ui.hands_free_on` / `ui.hands_free_off` si besoin).

## Hors scope
- Pas de VAD continuous-mic full si trop gros — si déjà un mode écoute continue existe, l'activer avec le toggle ; sinon le toggle = JeV filtre + libellé honnête « n'intervient que si on t'adresse ».
- Pas de purge, pas de commit sauf si demandé.

## OUT
- `nights/2026-09-20-OUT-PRESENCE-JEV-MAINS-LIBRES.md`
- `nights/2026-09-20-EXIT-PRESENCE-JEV-MAINS-LIBRES.txt` (0=OK)
Miroir aussi sous `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\`

## Preuve
- Presence relancée : bouton visible.
- Log hostagent : avec ON → lignes `JEV` ; avec OFF → pas d'ignore JeV.
- `python -m py_compile native/presence/app.py native/presence/onboarding.py`