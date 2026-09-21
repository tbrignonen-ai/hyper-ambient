# Correctif urgent 2 : forcer l'appel d'outil quand l'utilisateur nomme un harnais

Bonjour, je suis Opus et je travaille pour Human IA. Merci encore — c'est la suite
directe du correctif routeur que tu viens de livrer, et c'est le dernier point bloquant.

## Ce que j'ai mesure moi-meme, ne le refais pas

Mon correctif precedent partait d'un diagnostic incomplet. Preuve executee ce soir, dans
le conteneur, sur la vraie chaine (`run_tool_loop` + le vrai registre + le vrai cerveau) :

    BRAIN: llama.cpp llamacpp
    OUTILS: ['ask_claude', 'ask_codex', 'calculer', 'web_search']
    CANAUX: []
    OUTILS APPELES: []
    TEXTE: Je ne peux pas ouvrir le bloc-notes sur le bureau...
    MANDATS EN COURS: []

Deux faits s'en deduisent :

1. **Le routeur n'est pas en service.** `dev/scripts/carte_figee.env` ligne 7 pose
   `BRAIN_SERVICE=llamacpp`, et `charger_carte_figee()` **ecrase** l'environnement
   (contrairement a `charger_env_local`, qui respecte une valeur deja posee). Ton
   court-circuit `nomme_un_harnais` reste juste et utile comme filet, mais il ne
   s'execute jamais aujourd'hui. **Ne touche pas a la carte figee** : c'est une decision
   de latence prise le 19 septembre, le local doit rester le regime normal.
2. **Les outils SONT bien presents** dans la charge utile (`ask_codex` est declare), et
   le modele local Granite 4.2 3B **choisit de ne pas les appeler**. Il repond en texte
   qu'il ne sait pas ouvrir de programme. Trois formulations differentes, trois refus.

Le probleme n'est donc pas la disponibilite de l'outil, c'est le **choix** du modele. Un
3B ne se laisse pas convaincre par du prompt : il faut lui retirer le choix.

## Le correctif demande

Quand l'utilisateur nomme explicitement un harnais, l'intention est connue avec
certitude. On force alors l'appel d'outil au lieu de l'esperer.

1. `src/brain/tool_loop.py` : `run_tool_loop` gagne un parametre nomme optionnel
   `tool_choice: Optional[Any] = None`. Il n'est transmis a `brain.query_streaming`
   **qu'a la premiere iteration** et **seulement si `tools_this_round` est non vide**.
   Aux iterations suivantes, plus jamais : un `tool_choice` maintenu ferait boucler le
   modele sur l'outil au lieu de formuler sa reponse.
2. `dev/scripts/serve_hostagent.py`, dans `_flux_brain` : avant d'appeler
   `run_tool_loop`, calculer le forcage. Si `nomme_un_harnais(prompt)` (importe depuis
   `src.brain.router`) ET que l'outil correspondant existe dans le registre, passer
   `tool_choice={"type": "function", "function": {"name": <nom_outil>}}`.
   Le nom d'outil se deduit de `extraire_harnais(prompt)` puis de la table
   `OUTIL_PAR_HARNAIS` de `src/brain/mandat.py` — les deux existent deja, ne les
   recris pas. Si le harnais deduit n'est pas dans le registre (pont non configure),
   ne force rien : le tour se deroule comme avant.
3. Commente la raison dans le code, brievement : mesure du 21/09, le modele local a
   refuse trois fois d'appeler `ask_codex` alors que l'outil lui etait declare ;
   nommer un harnais est une intention sans ambiguite, on retire donc le choix.

## Tests demandes (TDD : rouge d'abord)

Dans `dev/tests/test_tool_loop_edges.py` :

- `tool_choice` fourni est present dans la charge utile de la PREMIERE iteration ;
- il est absent de la seconde iteration (apres execution d'un outil) ;
- il est absent quand `tools_this_round` est vide (plafond atteint) ;
- sans `tool_choice`, la charge utile est **identique** a aujourd'hui (non-regression).

Et un test du cablage cote serveur si un banc existe deja pour `_flux_brain` ; sinon
teste au moins la fonction de deduction du nom d'outil a partir du prompt, y compris le
cas « harnais nomme mais pont absent du registre » -> aucun forcage.

## Contraintes

- Fichiers autorises : `src/brain/tool_loop.py`, `dev/scripts/serve_hostagent.py`,
  `dev/tests/test_tool_loop_edges.py`. Rien d'autre. **Ne touche pas a
  `dev/scripts/carte_figee.env` ni a `.env.local`.**
- Aucune commande git.
- Colle la sortie de :
  `python -m pytest dev/tests/test_tool_loop_edges.py dev/tests/test_router_outils.py dev/tests/test_mandat.py -q`
- Compte rendu dans `nights/2026-09-21-OUT-CURSOR-FORCER-OUTIL-HARNAIS.md`.
