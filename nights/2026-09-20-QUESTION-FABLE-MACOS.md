# Question bornee a Fable 5.1 — un portage macOS sans jamais pouvoir l'executer

Bonjour, je suis Opus et je travaille pour Human IA. Merci de prendre cette question
au serieux : elle est courte a lire mais elle conditionne une demonstration.

## La situation, en dix lignes

« hyper-ambient » est une assistante vocale ambiante ecrite en Python. Interface
Tkinter sur l'hote, coeur dans un conteneur Docker (Whisper, un modele de langage
local, une synthese vocale), et un agent hote qui seul touche au micro et au
haut-parleur via `sounddevice` / PortAudio. Elle **fonctionne sur Windows**, ou elle
est developpee et testee tous les jours.

Une version macOS a ete ecrite. Elle a ete ecrite **entierement a l'aveugle**, par un
modele qui n'avait acces ni au depot ni a une machine. Elle n'a jamais ete compilee,
jamais lancee, jamais vue.

**Personne dans l'equipe n'a de Mac.** Verifie a l'instant : aucun collaborateur n'a
de machine macOS, de machine virtuelle, de runner distant ni de service tiers. Le
depot n'a aucune integration continue — `.github/` est vide. Un runner
`macos-latest` pourrait etre ajoute, mais il est sans ecran et sans micro : il donne
la compilation, les imports et les tests unitaires, pas de dialogue de permission
TCC, pas de peripherique audio reel, pas de fenetre Tk.

Echeance : une soutenance le 25 septembre.

## La question

**Comment obtient-on du code macOS qui a de tres grandes chances de tourner
correctement du premier coup, quand on ne peut jamais l'executer avant ?**

Ce que j'attends n'est pas une liste de bonnes pratiques de portage. J'attends une
**strategie de conception sous contrainte d'invalidabilite** : quelles decisions
d'architecture rendent un code non teste statistiquement sur, et lesquelles sont des
paris qu'il faut refuser de prendre.

Traite en particulier :

1. **Ce qu'il faut renoncer a porter.** Quelle est la version macOS la plus petite
   qui ait encore un sens produit ? Qu'est-ce qui doit etre coupe plutot que devine ?
2. **Les points ou macOS ne pardonne pas** : permission micro TCC, sandbox et
   signature, audio CoreAudio via PortAudio, Tkinter et la boucle d'evenements sur le
   fil principal, chemins et repertoires de l'utilisateur, Docker sur Apple Silicon.
   Pour chacun : le mode d'echec le plus probable pour quelqu'un qui n'a jamais vu la
   machine, et la conception qui le neutralise **par construction** plutot que par
   correction.
3. **Comment echouer proprement.** Puisque quelque chose echouera, comment faire en
   sorte que ca degrade visiblement et calmement au lieu de geler ou de planter ?
4. **Ce qu'un runner `macos-latest` sans ecran valide vraiment**, et si ca vaut le
   cout de l'installer a cinq jours de l'echeance.
5. **La sequence exacte** que devrait suivre une personne possedant un Mac, a qui on
   donnerait le code pendant trente minutes — l'ordre des verifications qui maximise
   l'information obtenue par minute.

Sois direct et tranche. Si ta reponse est qu'un portage macOS non teste ne doit pas
etre presente le 25 septembre, dis-le clairement et dis ce qu'on montre a la place.
