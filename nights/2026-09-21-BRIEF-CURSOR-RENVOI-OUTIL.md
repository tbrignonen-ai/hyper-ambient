# Nuit A7 — elle doit renvoyer vers l'outil pour le détail

Excellent travail sur la racine Tk : tu as trouvé la vraie cause, et tu as vu que le
second mécanisme était un défaut du produit et pas seulement de la suite. C'est exactement
la distinction qu'il fallait faire.

Dernier point de la nuit. Périmètre : `src/brain/`, `dev/scripts/serve_hostagent.py`,
`dev/tests/`. Aucune commande git. Le dépôt est déjà poussé, donc cette tâche doit être
verte avant d'être reprise — ne laisse rien à moitié.

## La consigne du fondateur, littérale

« Clairement, pour du dev intensif, hyper-ambient n'est pas l'outil adapté. Il peut gérer
des tâches simples, mais il n'y a pas d'interface visuelle donc l'utilisateur devrait
regarder les résultats sur Codex ou Claude Code. Hyper-ambient peut le préciser. Elle
donne le résumé (grâce au modèle distant) puis peut encourager brièvement à consulter
l'outil pour plus d'informations. »

C'est écrit dans le README, mais le produit ne le dit pas. Il faut que **la voix** le dise.

## Ce que je veux

Quand un mandat revient d'un harnais, elle prononce son résumé, puis — seulement quand
c'est utile — une invitation courte à aller voir le détail dans l'outil. Par exemple :
« Le détail est dans Codex si tu veux le lire. »

Trois exigences, et la troisième est la plus importante :

1. **Une seule phrase, courte.** Elle s'ajoute au résumé, elle ne le remplace pas. Le
   registre du produit est calme et bref ; pas de formule commerciale, pas de « n'hésite
   pas à ».
2. **Le nom du bon outil.** Elle renvoie vers le harnais qui a réellement travaillé, celui
   dont le mandat porte le nom.
3. **Pas à chaque fois.** « Le dossier src/brain contient 16 fichiers Python » est une
   réponse complète : renvoyer vers Codex après ça serait absurde et vite agaçant. La
   phrase n'a de sens que lorsque le résumé est une **réduction** d'un résultat plus riche.

Pour le troisième point, choisis un critère que tu peux défendre, et explique-le en
commentaire. Le contrat de sortie des harnais porte déjà `resume_voix` **et**
`resultat_complet` : l'écart entre les deux est le signal le plus honnête dont tu disposes.
Une réponse dont le résultat complet tient dans le résumé n'a rien de plus à montrer. Fixe
le seuil sur cette base plutôt que sur le nombre de mots prononcés, et dis-moi la valeur
que tu retiens et pourquoi.

Prévois que ce comportement se désactive : un réglage dans les menus de configuration,
avec la valeur par défaut activée.

## Tests

TDD, rouge d'abord. Un résultat riche produit l'invitation, un résultat court ne la produit
pas, l'invitation nomme le harnais qui a travaillé, elle est absente quand le réglage est
désactivé, et un tour sans mandat n'est pas affecté.

## Vérification attendue

Avec l'outil écrit, et colle les deux sorties brutes :

    python dev/scripts/parler_ecrit.py "Demande a Codex combien de fichiers Python contient le dossier src/brain."
    python dev/scripts/parler_ecrit.py "Demande a Codex de m'expliquer comment fonctionne le routeur dans src/brain/router.py."

La première ne doit pas renvoyer vers l'outil, la seconde doit le faire. Puis la suite
complète dans le conteneur, et les six fichiers Tk sur l'hôte.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-RENVOI-OUTIL.md`.
