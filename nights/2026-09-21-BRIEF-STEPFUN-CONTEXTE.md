Bonjour, je suis Opus et je travaille pour Human IA. Tu n'as ni accès au disque ni
harnais : tout le contexte nécessaire est écrit ci-dessous, ne suppose rien d'autre et
n'invente aucun contenu de fichier. Rends un document de conception, pas du code prêt à
coller.

# La demande

Le fondateur d'hyper-ambient a écrit, dans une liste de points à traiter :
« Aussi il faut une gestion du contexte pour hyper-ambient qui soit cohérente. »

C'est tout ce qu'il a dit. Ton travail est de concevoir cette politique de contexte et
d'en écrire la spécification, en justifiant chaque choix.

# Ce qu'est hyper-ambient

Une voix ambiante locale sur un ordinateur Windows. L'utilisateur parle, elle répond à
voix haute. Elle sait aussi confier du travail à des harnais de développement déjà
installés sur la machine — Codex, Claude Code, Cursor — et rapporter leur réponse.

Deux modes d'écoute :

- **Appui sur un bouton** : l'utilisateur maintient ou appuie pour parler.
- **Mains libres** : le micro est ouvert en permanence, l'utilisateur ne touche à rien.
  Un service distant appelé JeV décide, pour chaque phrase captée, si elle s'adresse à
  l'assistante ou non. Une phrase qui ne lui est pas adressée est ignorée. Une fois
  qu'un échange commence, une fenêtre de conversation de 30 secondes s'ouvre : pendant
  cette fenêtre, JeV n'est plus consulté et tout ce qui est dit est traité comme
  adressé à elle.

# L'architecture du raisonnement

Deux canaux derrière une même façade :

- **Le canal réflexe** : un modèle local de 3 milliards de paramètres (Granite 4.2,
  quantifié) servi par llama.cpp. Il répond en 650 ms bout en bout. Il tient le temps
  réel : politesses, questions courtes, réponses immédiates. Il n'a aucun outil.
- **Le canal profond** : un modèle distant (MiniMax M3) appelé par API. Il répond en
  2,2 secondes environ. C'est lui, et lui seul, qui a le droit d'appeler les harnais.

Un classifieur local tranche à chaque tour entre les deux, avec une grammaire contrainte
qui ne peut produire que deux jetons. Il coûte environ 90 ms à chaud. Deux règles le
court-circuitent déjà : un tour qui nomme un harnais escalade toujours, et un échec du
classifieur escalade par défaut plutôt que de répondre localement à tort.

Pendant l'attente du canal distant, elle prononce une amorce courte (« Un instant. »,
« Je vérifie. ») parce qu'un silence de plusieurs secondes dans une conversation parlée
est interprété comme une panne.

# L'état actuel de la gestion du contexte, tel qu'il est

C'est ce qui doit être remis à plat. Voici ce qui existe :

1. **Un historique de conversation** est tenu et joint aux appels du modèle. Sa taille
   n'est bornée par aucune règle explicite liée à la parole ; il grandit avec l'échange.
2. **Les résultats d'outil sont éphémères** : le résultat d'un appel à un harnais est
   injecté dans le tour qui suit immédiatement cet appel, puis purgé. Il ne revient
   jamais aux tours ultérieurs. La raison est qu'un long résultat technique réinjecté
   en boucle polluait la parole.
3. **Le classifieur ne voit le tour précédent que si l'énoncé courant fait moins de
   25 caractères.** Motif mesuré : un énoncé court comme « vas-y » ou « et alors ? » ne
   veut rien dire seul ; mais au-delà, joindre le tour précédent déréglait le jugement,
   une question autonome se faisant classer « réflexe » dès qu'une politesse la
   précédait, et recevant alors une réponse locale fausse.
4. **Les deux canaux partagent le même historique**, alors qu'ils n'ont ni la même
   fenêtre de contexte, ni la même latence, ni les mêmes capacités.
5. **Les mandats sont asynchrones** : quand elle confie une tâche à un harnais, elle
   l'accuse immédiatement à voix haute, le tour se termine, et la réponse arrive
   plusieurs dizaines de secondes plus tard — annoncée dans un tour ultérieur, qui n'a
   aucun rapport conversationnel avec le tour où la demande a été faite. Au plus trois
   mandats simultanés.
6. Une nouveauté de cette nuit : **les conversations sont désormais écrites sur le
   disque local**, en Markdown, un fichier par conversation, relisible par l'utilisateur.

# Les tensions que ta conception doit résoudre

- Un modèle local de 3 milliards de paramètres se dégrade vite quand l'historique
  s'allonge, bien avant la limite technique de sa fenêtre. Le modèle distant, lui,
  supporte beaucoup plus. Faut-il deux historiques distincts, un historique commun
  tronqué différemment à l'envoi, ou un résumé ?
- Un tour traité localement et le suivant traité à distance doivent donner à
  l'utilisateur l'impression d'une seule interlocutrice. Qu'est-ce qui doit
  impérativement traverser la frontière entre les deux canaux ?
- La parole est le seul canal de sortie. Tout ce qui est gardé en contexte finit par
  influencer ce qui est prononcé. Qu'est-ce qui mérite d'être retenu d'un tour :
  la transcription brute, la réponse prononcée, les deux, ou une forme réduite ?
- En mains libres, des phrases peuvent être captées sans être adressées à elle.
  Entrent-elles dans le contexte ? Et une phrase jugée non adressée, mais qui précède
  immédiatement une phrase adressée, est-elle un contexte utile ou un parasite ?
- La réponse d'un harnais arrive hors du tour où elle a été demandée. Comment la
  raccrocher au fil de la conversation pour que « et alors, qu'est-ce qu'il a dit ? »
  trente secondes plus tard ait un sens ?
- Quand une conversation est-elle finie ? Après combien de silence la mémoire doit-elle
  se vider, et faut-il le dire à l'utilisateur ?

# Le format de ta réponse

Un document en français, structuré, qui contient :

1. **Les principes** : trois à cinq règles courtes qui décident de tout le reste.
2. **La politique détaillée** : ce qui est retenu, sous quelle forme, pendant combien de
   temps, et ce qui est envoyé à chacun des deux canaux. Sois précis sur les bornes
   (nombre de tours, durée, taille) et justifie chaque valeur — un chiffre sans raison
   sera rejeté.
3. **Les cas limites** énumérés dans la section précédente, traités un par un.
4. **Ce que l'utilisateur perçoit** : ce qui change pour lui, et ce qu'il faut
   éventuellement lui dire à voix haute (par exemple à la fin d'une conversation).
5. **Le plan d'implémentation** : dans quel ordre, et ce qui est vérifiable par un test.
6. **Ce que tu déconseilles** et pourquoi — les fausses bonnes idées que tu as écartées.

Contrainte de sobriété : le budget mémoire graphique de la machine est de 8 Go tous
étages confondus. Une solution qui demande un second modèle chargé en mémoire sera
rejetée. Le résumé par modèle, s'il est proposé, doit s'appuyer sur un modèle déjà en
service.
