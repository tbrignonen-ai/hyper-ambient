# Correctif urgent : un tour qui nomme un harnais ne doit JAMAIS partir en REFLEXE

Bonjour, je suis Opus et je travaille pour Human IA. Merci de ton aide, c'est sur le
chemin critique : le depot passe en public ce soir.

## Le defaut, mesure en conditions reelles

Journal du host-agent, ce soir, mode mains libres :

    TRANSCRIPT "Envoie une requete a Codex qui ouvre le programme calque.exe sur le bureau."
    BRAIN : "Je ne peux pas ouvrir ou executer des programmes comme << calque.exe >>..."
    BRAIN : TTFT 75 ms

Trois formulations differentes de la meme demande ont recu la meme reponse : un refus.
Aucun mandat n'a ete depose, aucun outil appele.

## La cause racine, deja identifiee — ne la re-cherche pas

`BRAIN_SERVICE=router`. Dans `src/brain/router.py`, `classify()` a range ces trois
enonces en `REFLEXE`. Or la voie REFLEXE appelle le modele local a travers
`sans_outils(kw)`, qui retire `tools` et `tool_choice` de la charge utile (ligne 96).
Le modele local se retrouve donc sans aucun outil, et fait la seule chose qu'il peut
faire : expliquer qu'il n'en a pas. TTFT 75 ms confirme la voie locale.

Le pilotage des harnais est LA fonctionnalite qui sera montree en soutenance. Elle est
actuellement inatteignable a la voix.

## Le correctif demande

Dans `src/brain/router.py` :

1. Ajouter une fonction de module `nomme_un_harnais(prompt: str) -> bool`. Elle
   reutilise la liste de noms qui existe deja dans `src/brain/mandat.py` — importe
   `_NOMS` ou, mieux, expose proprement la constante depuis `mandat.py` plutot que de
   redupliquer la regex. Les noms couverts sont : codex, claude, muse, cursor, en
   frontieres de mot, insensible a la casse.
2. Dans `classify()`, court-circuiter AVANT l'appel au classifieur : si
   `nomme_un_harnais(prompt)`, retourner directement
   `{"route": "escalate", "latency_ms": 0.0, "verdict": "HARNAIS"}`.
   Justification a ecrire en commentaire dans le code : nommer un harnais est par
   definition une demande d'action, jamais un reflexe ; et la voie reflexe est la seule
   qui n'a pas d'outils, donc la seule ou la demande ne peut pas aboutir.
3. Le repli de fin de `query_streaming` (voie profonde en echec -> reflex) doit rester
   tel quel : si le distant tombe, mieux vaut une reponse locale qu'un silence.

## Tests demandes (TDD : ecris le test, vois-le rouge, puis corrige)

Dans `dev/tests/test_router_outils.py` :

- un enonce nommant Codex est escalade sans appel au classifieur (verifie que le
  client HTTP n'a PAS ete appele) ;
- idem pour Claude, Cursor, Muse ;
- un enonce ordinaire (« Bonjour. ») continue de passer par le classifieur et reste
  REFLEXE ;
- la casse et la ponctuation ne comptent pas (« demande a CODEX, stp »).

## Contraintes

- Ne touche a aucun autre fichier que `src/brain/router.py`, `src/brain/mandat.py`
  (uniquement pour exposer la constante de noms) et `dev/tests/test_router_outils.py`.
- Aucune commande git : ni branche, ni commit, ni stash. C'est mon perimetre.
- Lance la suite ciblee et colle la sortie :
  `python -m pytest dev/tests/test_router_outils.py -q`
- Ecris ton compte rendu dans `nights/2026-09-20-OUT-CURSOR-ROUTEUR-HARNAIS.md` :
  ce que tu as change, la sortie des tests, et tout doute qui te reste.
