# Brief — Ce qui est configurable dans l'onboarding, et une seconde instance vierge

Bonjour, c'est encore Opus, Human IA. Merci pour ton audit d'ecarts, il est excellent.

## Partie 1 — Repondre a une question precise du fondateur

Il demande : **qu'est-ce qui est configurable dans l'onboarding de hyper-ambient ?**
Il ne se souvient plus de ce qui avait ete decide. Il cite de memoire : le modele
externe, la connexion avec les harnais, la connexion avec JeV, le tout assiste par
le modele local.

Va chercher la reponse dans ce qui a **deja ete ecrit et decide**, ne l'invente pas :

- `nights/2026-09-14-CODEX-ONBOARDING-DESIGN.md`
- `nights/2026-09-14-MUSE-ONBOARDING-UX.md`
- `nights/2026-09-15-CURSOR-DESIGN-ONBOARDING.md`
- `nights/2026-09-17-MUSE-ONBOARDING-LLM-V1.md`
- `nights/2026-09-20-ONBOARDING-OUT.md`
- ton propre `nights/2026-09-20-OUT-CODEX-ONBOARDING-ECARTS.md`
- `native/presence/onboarding.py` — ce qui est REELLEMENT implemente
- `dev/scripts/carte_figee.env` et `.env.local` — **sans jamais afficher aucune valeur
  de cle**, seulement les noms de variables

Produis un tableau : chaque element configurable, **ou** il a ete decide (le fichier),
s'il est **implemente** ou seulement **specifie**, et **ce qui se passe si on ne le
configure pas**.

Couvre au minimum : langue, raccourci clavier, mains libres, contraste, modele local,
modele distant d'escalade, cles des harnais Codex et Claude, cle JeV, recherche web,
peripheriques audio, voix.

Dis clairement ce qui est **assiste par le modele local** (l'onboarding conversationnel)
et ce qui est un **formulaire classique**.

## Partie 2 — Permettre une seconde instance non configuree

Le fondateur veut lancer une deuxieme instance vierge pour tester l'onboarding,
**sans perturber la premiere**, qui tourne et sur laquelle il continue ses tests.
`native/presence/app.py` accepte deja `--config`.

Verifie et rends cela reellement possible : profil de configuration separe, journal
separe, et surtout **aucun partage d'etat** avec l'instance en cours — fichier de
configuration, journal, verrou eventuel, port.

**Signale franchement tout conflit qui resterait.** Par exemple si les deux instances
se disputent le micro ou le websocket de l'agent hote, dis-le plutot que de pretendre
que ca marche. Un conflit connu vaut mieux qu'une surprise pendant un test.

Livre dans ton rapport **la commande exacte, en syntaxe PowerShell**, copiable telle
quelle depuis n'importe quel repertoire, pour lancer cette seconde instance vierge.
Le fondateur travaille dans PowerShell : pas de `cd /d`, pas de `start`, pas d'outils
Unix. Utilise `Set-Location` et `Start-Process`, et mets entre guillemets les chemins
qui contiennent des espaces.

## Contraintes

Tu peux modifier le code si c'est necessaire pour la partie 2, mais reste minimal et
ne touche a rien d'autre que ce qui concerne l'isolation des instances.
**N'execute aucune commande git.**

Reference de la suite de tests : `docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py`
donne aujourd'hui **1323 passes, 5 echecs pre-existants**. Aucun echec nouveau.

Rapport dans `nights/2026-09-20-OUT-CODEX-ONBOARDING-CONFIGURABLE.md`.
