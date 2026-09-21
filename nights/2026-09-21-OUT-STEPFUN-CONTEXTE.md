**Document de conception — Politique de contexte pour hyper-ambient**

---

## 1. Principes

**P1. La parole est l’unité de mémoire.**  
Seul ce qui peut être, a été, ou sera prononcé entre dans le contexte vocal. Les artefacts techniques internes (dumps de harnais, JSON, traces) sont écrits sur disque mais jamais réinjectés dans la fenêtre de conversation.

**P2. Deux canaux, une même voix.**  
Les canaux réflexe et profond ne partagent pas la même fenêtre, mais ils partagent un noyau minimal commun — le *spine* — qui garantit que l’utilisateur n’entend jamais de rupture de personne entre un tour local et un tour distant.

**P3. L’oubli est borné par la parole, pas par les tokens.**  
Les limites sont exprimées en tours parlés et en secondes de silence, jamais en taille de fenêtre technique. Un modèle de 3 milliards de paramètres se dégrade en cohérence conversationnelle bien avant sa limite de contexte ; c’est cette dégradation que la politique encadre.

**P4. L’adresse est le filtre d’entrée.**  
En mains libres, une phrase non adressée à l’assistante n’entre pas dans l’historique conversationnel. Une seule exception tolérée : la phrase non adressée immédiatement précédente, conservée quelques secondes dans un tampon d’amorce pour lever une anaphore.

**P5. L’asynchronisme est explicite et traçable.**  
Un mandat confié à un harnais possède sa propre fiche dans un registre de mandats. Sa réponse n’est parlée que lorsqu’elle est raccrochée au fil, et seule sa forme parlée — jamais son contenu brut — retourne dans l’historique.

---

## 2. Politique détaillée

### 2.1 Le tour parlé : l’atome de mémoire

Chaque tour de conversation est stocké sous la forme d’un **tour parlé** contenant :

* `user_norm` : transcription normalisée de l’utilisateur, tronquée à **120 caractères** ;
* `assistant_spoken` : texte exact qui a été prononcé par la voix, tronqué à **200 caractères** ;
* `timestamp` : horodatage de fin de tour ;
* `origine` : `reflexe` ou `profond` ;
* `mandate_ref` : identifiant de mandat si le tour livre ou accuse une tâche externe.

**Justification.** La réponse interne du modèle, les amorces de réflexion et les résultats techniques ne sont pas retenus dans la mémoire vive : ils pollueraient la parole. La transcription brute de l’utilisateur est conservée sur disque dans le Markdown, mais seule la forme compacte `user_norm` alimente les canaux.

### 2.2 Le noyau partagé (Spine)

Les **3 derniers tours parlés complets** (6 messages : 3 paires utilisateur/assistante) sont conservés dans une mémoire commune obligatoirement lisible par les deux canaux.

**Justification.** Trois tours couvrent le présent et le passé immédiat nécessaires à la continuitité de voix (« tu disais ? », « comme je l’ai dit »). C’est assez court pour que le canal réflexe ne soit pas perturbé, et assez long pour que le canal profond ne commence pas à froid après une bascule.

### 2.3 Projection pour le canal réflexe

Le canal réflexe reçoit :

* le *spine* des 3 derniers tours ;
* une **ligne de session** d’une phrase : le dernier sujet explicite ou le mandat actif le plus récent.

Plafond dur : **3 tours / 512 tokens** pour l’ensemble du prompt.

**Justification.** Un modèle local de 3 milliards de paramètres perd la cohérence au-delà de 2 à 3 échanges ; sa fenêtre technique le permet, mais sa qualité de suivi s’effondre. Le budget de latence de 650 ms bout en bout impose aussi un prompt court : au-delà de 512 tokens, le pré-remplissage consomme une part disproportionnée du budget et fait sortir du temps réel. Le classifieur envoie vers le réflexe des échanges majoritairement courts (politesses, confirmations, questions simples) qui n’ont pas besoin de plus.

### 2.4 Projection pour le canal profond

Le canal profond reçoit :

* le *spine* des 3 derniers tours ;
* jusqu’à **12 tours antérieurs supplémentaires** en forme compacte (`user_norm` + `assistant_spoken`) ;
* le **registre des mandats actifs** (3 maximum), avec pour chacun : le harnais, la demande parlée initiale, l’état, et le cas échéant le résumé parlé du résultat.

Plafond dur : **15 tours visibles / 3 000 tokens**.

**Justification.** Le modèle distant absorbe sans dégradation perceptible une quinzaine de tours ; c’est la profondeur nécessaire pour clarifier une tâche de harnais, itérer sur un mandat, ou répondre à une question qui fait référence à un échange antérieur. Au-delà, le coût API et la latence de 2,2 s ne sont plus justifiés par un gain conversationnel marginal.

### 2.5 Le classifieur local

Le classifieur reçoit une fenêtre adaptative :

* **Si l’énoncé courant fait strictement plus de 25 caractères** : l’énoncé seul.
* **Si l’énoncé courant fait 25 caractères ou moins** : l’énoncé + le tour précédent, chaque champ tronqué à **80 caractères**.

**Justification.** Le seuil de 25 caractères sépare les énoncés autonomes des anaphores (« vas-y », « et alors ? », « fais-le »). Fournir le tour précédent pour les énoncés longs faisait dériver le classifieur vers le canal réflexe dès qu’une politesse précédait une question technique ; la question héritait alors du ton léger du tour précédent et recevait une réponse locale fausse. La troncature à 80 caractères limite cet effet de dilution tout en préservant l’ancrage nécessaire aux énoncés courts.

### 2.6 Mandats asynchrones et registre

Chaque mandat possède une fiche dans un **registre de mandats** :

* `id`, `harnais`, `demande_parlée` (forme compacte), `état` (`en_cours`, `livré`, `échoué`), `résultat_parlé` (forme compacte produite à la livraison).

Règles :

* Le résultat technique brut du harnais n’entre **jamais** dans le contexte vocal. Il est écrit sur disque dans le Markdown de la conversation.
* À la réception, le canal profond (ou un gabarit de livraison) produit un `résultat_parlé` de **2 à 3 phrases maximum**. Ce texte est stocké dans la fiche.
* La livraison n’est pas automatique : si l’utilisateur est encore en conversation, l’assistante peut annoncer spontanément ; sinon, le résultat attend.
* Le `résultat_parlé` reste dans l’historique conversationnel pendant **5 tours** après sa livraison effective, puis il est retiré du contexte vocal (il reste sur disque).

**Justification.** Cinq tours permettent une question de suivi immédiate (« et alors ? ») et une clarification, sans faire stagner un résumé technique dans la bouche de l’assistante pendant toute la conversation. Le registre permet de rattacher un résultat tardif à sa demande, même si dix tours et deux sujets sont passés entre-temps.

### 2.7 Mains libres et phrases non adressées

* Une phrase jugée non adressée par JeV **n’entre pas** dans l’historique conversationnel.
* Exception unique : la dernière phrase non adressée immédiatement précédente, datant de **moins de 5 secondes**, est conservée dans un tampon d’amorce. Si l’énoncé suivant est adressé et fait **15 caractères ou moins**, ce tampon est fourni aux canaux marqué `[ambiant]`. Dans tous les autres cas, il est effacé sans laisser de trace dans le contexte vocal.

**Justification.** Une phrase captée sans être adressée est un parasite pour le modèle : elle introduit un sujet, un ton ou un interlocuteur tiers. La fenêtre de 5 secondes et la limite de 15 caractères sont assez étroites pour ne capter que le cas d’usage réel — une anaphore (« fais-le », « résume-le ») qui fait référence à une instruction que l’utilisateur vient de donner à quelqu’un d’autre dans la pièce.

### 2.8 Fin de conversation et purge

* **Mains libres** : la conversation se ferme après **30 secondes de silence** mesurées depuis le dernier tour parlé.
* **Bouton** : la conversation se ferme après **60 secondes de silence**.

À la fermeture :

* l’historique complet est écrit sur disque dans le fichier Markdown de la conversation ;
* la mémoire vive est purgée : *spine*, projections, tampon d’amorce ;
* les mandats encore `en_cours` restent dans un registre persistant léger, détaché de l’historique conversationnel, pour pouvoir être livrés dans une session ultérieure si l’utilisateur les rappelle.

**Justification.** Les 30 secondes en mains libres reprennent la fenêtre existante de JeV : au-delà, la probabilité que la prochaine phrase appartienne à une nouvelle conversation l’emporte. Les 60 secondes en bouton laissent à l’utilisateur le temps de rappuyer après une réflexion ; au-delà, l’échange est considéré comme terminé. Purger évite qu’une session ancienne ne pollue une session neuve.

---

## 3. Cas limites

| Tension | Traitement |
|---|---|
| **Historique long, deux canaux** | Pas de résumé. Un *spine* de 3 tours est commun ; le réflexe s’arrête là, le profond y ajoute 12 tours compactés. Le disque garde tout, le contexte vocal projette. |
| **Continuité vocale entre canaux** | Le *spine* contient le texte exact prononcé au tour précédent. Le canal profond voit donc ce que l’utilisateur vient d’entendre, pas une trace interne. |
| **Forme retenue par tour** | La paire (`user_norm`, `assistant_spoken`). La transcription brute et les réponses internes sont exclues du contexte vocal. |
| **Phrases non adressées en mains libres** | Exclues par défaut. Seule la phrase non adressée < 5 s immédiatement antérieure est conservée, et uniquement si l’énoncé suivant est adressé et ≤ 15 caractères. |
| **Mandat asynchrone hors tour** | Un registre de mandats conserve la demande parlée et, à réception, un résumé parlé. La question « et alors ? » est résolue par consultation du registre, pas par recherche dans un historique linéaire. |
| **Fin de conversation** | 30 s (mains libres) ou 60 s (bouton) de silence déclenchent la purge mémoire. Aucune annonce systématique ; message de garde uniquement si des mandats sont en cours. |
| **Classifieur et tour précédent** | Fenêtre adaptative : énoncé seul si > 25 caractères ; énoncé + tour précédent tronqué à 80 caractères sinon. |

---

## 4. Ce que l’utilisateur perçoit

* **Une seule interlocutrice.** Après une bascule réflexe/profond, la voix ne change pas de registre brutalement : le canal distant a vu le texte exact du tour local précédent.
* **Une parole plus propre.** Les résultats de harnais ne sont plus lus en boucle ; ils sont résumés en deux ou trois phrases au moment où ils sont livrés, puis disparaissent du contexte vocal.
* **Moins de blancs interminables.** Le canal réflexe garde un prompt court, donc son temps de réponse reste dans le budget des 650 ms même après plusieurs échanges.
* **Des mandats qui ne se perdent pas.** Si l’utilisateur demande « qu’est-ce qu’il a dit ? » trente secondes après avoir lancé Codex, l’assistante retrouve la fiche du mandat et répond sans redemander.
* **En fin de conversation**, rien n’est annoncé si le silence est naturel. En revanche, si un mandat était encore en cours au moment de la fermeture, elle prononce une phrase de garde du type : *« Je garde un œil sur Codex. »*

---

## 5. Plan d’implémentation

1. **Structurer le tour parlé.**  
   Remplacer le stockage actuel par l’atome `user_norm` / `assistant_spoken` / `origine` / `mandate_ref`.  
   *Test :* vérifier qu’aucune réponse interne de modèle ni dump technique n’est écrit dans la structure de contexte vive.

2. **Mettre en place le spine et les projections.**  
   Implémenter la mémoire commune de 3 tours et les fenêtres différenciées (réflexe 3 tours / 512 tokens ; profond 15 tours / 3 000 tokens).  
   *Test :* faire passer 10 échanges, mesurer la latence du canal réflexe et la cohérence des réponses ; vérifier que le canal profond retrouve une information du tour 4 quand on la sollicite au tour 12.

3. **Réformer le classifieur.**  
   Implémenter la fenêtre adaptative (> 25 caractères seul ; ≤ 25 caractères + tour précédent tronqué à 80 caractères).  
   *Test :* jeu d’énoncés composé de questions longues précédées de politesses, et d’anaphores courtes. Mesurer le taux de mauvaise escalade / mauvaise rétention.

4. **Implémenter le registre de mandats et la livraison parlée.**  
   Créer les fiches de mandat, produire le `résultat_parlé` à la réception, et permettre la résolution de « et alors ? ».  
   *Test :* lancer un mandat, simuler une arrivée tardive de 40 s, poser la question de suivi, vérifier que la réponse correspond au bon mandat.

5. **Gérer le tampon ambiant en mains libres.**  
   Conserver la phrase non adressée < 5 s, l’injecter marquée `[ambiant]` uniquement si l’énoncé suivant est adressé et ≤ 15 caractères.  
   *Test :* enregistrer une phrase non adressée puis une anaphore courte ; vérifier que le contexte est utilisé sans être prononcé.

6. **Bornes de fin et purge.**  
   Implémenter les minuteurs de 30 s / 60 s, la purge mémoire, et le message de garde si mandats en cours.  
   *Test :* simuler un silence, vérifier que la mémoire vive est vide, que le disque contient la trace, et qu’une nouvelle phrase ouvre une session neuve.

---

## 6. Ce que je déconseille

* **Le résumé par modèle local.** Un modèle de 3 milliards de paramètres déjà sollicité en temps réel ne peut pas produire un résumé fiable sans bloquer le canal réflexe pendant plusieurs secondes. Et un second modèle de résumé est exclu par le budget de 8 Go de VRam. Je préfère une projection par troncature et par oubli borné, plus prédictible.
* **Deux historiques totalement séparés.** Sans *spine* commun, l’utilisateur entendrait une bascule de personnalité à chaque changement de canal. La continuité vocale exige un minimum partagé.
* **Réinjecter les résultats techniques bruts.** C’est le comportement actuel qui polluait la parole. La séparation disque / contexte vocal est la bonne frontière.
* **Borner l’historique en tokens plutôt qu’en tours.** Un modèle de 3 milliards de paramètres se dégrade en tours conversationnels, pas seulement en tokens. Une limite en tokens laisserait passer des historiques trop longs mais peu denses.
* **Laisser JeV tourner après la fenêtre de 30 s.** Cela crée une charge distante inutile et un risque de double détection. La fenêtre de conversation doit être franche.
* **Annoncer chaque fin de conversation à voix haute.** Cela deviendrait une interruption systématique. La fermeture doit être silencieuse, sauf message de garde pour un mandat en cours.