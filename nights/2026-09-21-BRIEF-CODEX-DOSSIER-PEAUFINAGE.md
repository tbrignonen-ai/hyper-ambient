# Nuit D — peaufiner les deux documents BGB, sans les dénaturer

Bonjour, je suis Opus et je travaille pour Human IA. Le fondateur dort ; il a demandé que
tu peaufines ses documents pendant la nuit. Tu travailles dans `D:\BGB Training\`.

## Les fichiers

À améliorer, ce sont tes propres versions écrites hier soir :

- `D:\BGB Training\BGB_BC02_Dossier_technique_COMPLETE.docx`
- `D:\BGB Training\BGB_BC02_Preparer_votre_soutenance_COMPLETE.docx`

**Interdiction absolue de modifier ou d'effacer les originaux** :
`BGB_BC02_Dossier_technique_a_completer.docx` et
`BGB_BC02_Preparer_votre_soutenance.docx`. Il l'a dit explicitement : « bien sûr des
nouvelles versions, n'effacez pas les originaux ».

`D:\BGB Training` est un coffre Obsidian. N'y crée ni dépôt git, ni fichier de travail
temporaire, ni dossier parasite. Si tu as besoin d'un brouillon, garde-le en mémoire.

## Le ton, qui est la consigne la plus importante

Ses mots : « il faut que ça sonne pas trop IA sur la partie du début. Je vais relire.
Mais un truc court et simple, qui sonne à peu près humain. Si vous mettez des chiffres
partout dans les cases, ça ne sonne pas du tout humain. »

Donc : des phrases de longueur inégale, peu de chiffres, aucune énumération à trois
termes systématique, pas de superlatif, pas de vocabulaire de plaquette commerciale. Il
relira lui-même ; ton travail est de lui donner un texte qu'il n'a pas honte de signer,
pas un texte impressionnant.

## Ce qui a changé dans le produit depuis hier soir — à refléter

Le document technique doit dire le vrai. Voici ce qui est devenu exact cette nuit, et que
tu peux affirmer :

- Le raisonnement est réparti sur deux canaux. Un modèle local de 3 milliards de
  paramètres tient le temps réel, mesuré à 650 ms bout en bout sur un tour ordinaire. Un
  modèle distant prend les tours difficiles et, surtout, c'est lui qui pilote les harnais
  de développement installés sur la machine — mesuré à 2,2 secondes sur un tour qui
  confie une tâche à Codex. Un classifieur local tranche entre les deux à chaque tour.
- Le pilotage des harnais fonctionne de bout en bout : la demande orale arrive, le canal
  distant appelle l'outil, un mandat est déposé, et la réponse est annoncée plus tard sans
  bloquer la conversation.
- Les conversations sont écrites en clair sur le disque local, relisibles par
  l'utilisateur, et ne sortent pas de la machine.
- Une limite assumée, qu'il veut voir écrite : pour du développement intensif,
  hyper-ambient n'est pas l'outil adapté. Il n'a pas d'interface visuelle ; il gère des
  tâches simples, donne un résumé, et invite à consulter Codex ou Claude Code pour le
  détail.
- macOS : le portage est écrit mais n'a jamais tourné sur une vraie machine. Ne le
  présente pas comme supporté.

N'invente aucun chiffre que je ne t'ai pas donné ici. Si une case appelle une mesure que
tu n'as pas, écris la phrase sans la mesure plutôt qu'avec une valeur inventée, et
signale-la-moi dans ton compte rendu.

## Le scénario de panne

Il a tranché le périmètre : « il faut une panne qui peut arriver chez un user, pas
forcément de mon côté, le dev ». Vérifie que le scénario retenu est bien du côté de
l'utilisateur final et qu'il est plausible — une dépendance absente, un service local
qui ne démarre pas, un micro occupé par une autre application — avec la détection, la
réaction du produit et le retour à la normale.

## Ce que tu rends

Les deux `_COMPLETE.docx` améliorés, et un compte rendu dans
`D:\BGB Training\MOTHER-dev\nights\2026-09-21-OUT-CODEX-DOSSIER-PEAUFINAGE.md` :
ce que tu as changé, les cases que tu n'as pas pu remplir faute d'information, et les
endroits où tu penses que le fondateur doit trancher lui-même.

Aucune commande git, nulle part.
