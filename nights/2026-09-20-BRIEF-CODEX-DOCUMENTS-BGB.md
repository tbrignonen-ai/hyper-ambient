# Brief — Rediger les deux documents BGB

Bonjour, c'est Opus, Human IA. Le fondateur t'a choisi pour cette tache parce que tu
ecris bien. Ses mots : « GPT est un bon ecrivain. »

## Le ton, avant tout le reste

C'est la consigne la plus importante du brief, plus importante que l'exhaustivite.

> « Il faut que ca ne sonne pas trop IA sur la partie du debut. Un truc court et simple,
> qui sonne a peu pres humain. Si vous mettez des chiffres partout dans les cases, ca ne
> sonne pas du tout humain. »

Concretement :

- **Des phrases, pas des tableaux.** Une case remplie de puces et de metriques trahit la
  machine immediatement.
- **Court.** Une case qui appelle trois phrases recoit trois phrases. Ne remplis pas
  l'espace disponible par principe.
- **Un chiffre seulement quand il porte une decision.** « Le premier son est passe de
  3,4 a 1 seconde, ce qui a rendu la conversation supportable » vaut mieux que dix
  mesures alignees. Vise **au plus deux ou trois chiffres par section**, choisis.
- **La premiere personne**, celle de quelqu'un qui a fait le travail et le raconte.
  Pas de « il a ete decide que », pas de « la solution permet de ».
- **Pas de superlatifs, pas de vocabulaire de plaquette commerciale.** Pas
  d'« innovant », « robuste », « performant », « state of the art ». Dire ce qui a ete
  fait suffit.
- Assumer les manques a voix haute plutot que de les enrober. Un jury repere l'enrobage.

## Les deux documents

Ils sont dans `D:\BGB Training\` :

- `BGB_BC02_Dossier_technique_a_completer.docx`
- `BGB_BC02_Preparer_votre_soutenance.docx`

**N'ECRASE JAMAIS LES ORIGINAUX.** Produis de nouvelles versions a cote, nommees
`BGB_BC02_Dossier_technique_COMPLETE.docx` et
`BGB_BC02_Preparer_votre_soutenance_COMPLETE.docx`.

`python-docx` version 1.2.0 est deja installe sur le Python de l'hote. **N'installe
aucun paquet, sous aucun pretexte** — ce Python sert a l'entrainement d'un modele et une
installation casserait ses dependances. Si une bibliotheque te manque, dis-le et arrete-toi.

Lis d'abord les deux fichiers pour decouvrir leur structure reelle : les cases, les
questions, les longueurs attendues. Ne suppose pas leur contenu.

## La matiere

Tout est deja ecrit, tu n'as presque rien a inventer :

- `nights/2026-09-20-TAQUET-BGB-PREFILL.md` et `nights/2026-09-20-TAQUET-BGB-COLLER.md`
  — des blocs deja rediges pour ces cases precises.
- `nights/2026-09-19-SUGGESTIONS-CASES-BGB.md`
- `nights/2026-09-20-OUT-CURSOR-CARTE-DOSSIER.md` — la carte section par section, avec
  l'inventaire des chiffres disponibles **et** la liste de ce qui est faux ou perime.
- `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` — schemas C4 a jour.

**Attention aux pieges signales par la carte du dossier**, respecte-les :

- Le produit s'appelle **hyper-ambient**, plus jamais « MOTHER » dans la prose. « MOTHER »
  reste legitime comme nom de depot, d'image Docker et de variable technique. Ne colle
  pas « Hyper Ambient (MOTHER) », retire la parenthese.
- **Ne recopie pas `ARCHITECTURE.md`** : son schema et ses prochaines etapes sont faux.
- `STATUS.md` et `STACK.md` datent du 2 septembre et decrivent encore Piper. La synthese
  vocale est **Magpie / Sofia**.
- Ne cite jamais un chiffre historique comme s'il etait l'etat actuel. La carte separe
  explicitement les deux.

## Ce qu'on ne peut pas remplir

Le travail n'est pas termine. **Vise 90 %, pas 100 %.** La ou une case demande un
resultat qui n'existe pas encore, ecris une phrase honnete a la place et **marque-la
clairement** entre crochets, par exemple `[A COMPLETER — en cours ce soir]`, pour que le
fondateur la retrouve d'un coup d'oeil en relecture. Ne fabrique aucun resultat.

## La section « scenario de panne » — deja tranchee, applique-la

Le fondateur a demande une panne qui arrive **chez un utilisateur**, pas une erreur de
developpement. C'est celle-ci :

**Le micro devient muet sans rien dire.** Chez un utilisateur, le micro tombe pour trois
raisons banales : une autre application le prend en exclusivite (Teams, Zoom, OBS, un
jeu) ; la permission est retiree, parfois par une mise a jour de Windows qui reinitialise
les reglages de confidentialite ; le casque Bluetooth se deconnecte ou change de profil
en pleine conversation.

L'interet de ce scenario est que **ca ne plante pas**. Le flux audio s'ouvre normalement
et livre du silence — ou, sur macOS, des zeros exacts. Du point de vue du code tout va
bien : le peripherique existe, la capture tourne, aucune exception n'est levee. Du point
de vue de l'utilisateur, l'assistante affiche « j'ecoute » indefiniment et ne reagit plus
jamais. C'est la pire panne possible pour une voix ambiante : elle ne crie pas, elle ment.
L'utilisateur parle dans le vide, se repete, et conclut que le produit ne marche pas.

La reponse de conception : **on ne surveille pas l'API, on surveille le signal.** Si cent
pour cent des echantillons sont a zero pendant une seconde et demie alors que le flux est
ouvert, ce n'est pas du silence — un vrai micro produit toujours du bruit de fond. C'est
un micro mort. Elle le dit alors a voix haute et indique quoi faire : « je n'entends plus
rien, verifie qu'aucune autre application n'utilise ton micro. » Pas une icone, pas une
ligne de journal : une phrase, parce que c'est un produit qui parle.

Si le document demande une seconde panne, prends **la perte de reseau** : l'assistante
continue de fonctionner parce que le modele est local ; seules l'escalade vers le modele
distant et la recherche web se degradent, et elle l'annonce au lieu de rester muette. Cela
montre que « local par defaut » etait une decision de robustesse et pas un slogan.

Le principe directeur a faire passer dans les deux cas : **le silence n'est jamais une
reponse acceptable.**

## Contraintes

- Aucune cle, aucun jeton, aucun secret dans les documents. Le depot passe public ce soir.
- N'execute **aucune** commande git.
- Ne modifie aucun fichier du depot `MOTHER-dev` : tu ne produis que les deux `.docx`
  nouveaux dans `D:\BGB Training\` et ton rapport.
- Si un `.docx` est verrouille par Word (fichier `~$` present), **arrete-toi et dis-le**
  plutot que de forcer.

Rapport court dans `nights/2026-09-20-OUT-CODEX-DOCUMENTS-BGB.md` : ce que tu as rempli,
ce que tu as laisse en `[A COMPLETER]` et pourquoi.
