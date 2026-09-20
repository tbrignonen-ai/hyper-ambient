**Principe de conception : l’onboarding est une naissance, pas une installation.**  
L’interface Tkinter n’est pas un assistant de configuration : c’est une couveuse. Tant que les modèles ne sont pas dans la VRAM, l’application reste volontairement muette et sans micro. Le premier basculement vers la voix n’est pas une fonctionnalité, c’est le premier cri — et il sert à demander la seule chose qu’on ne peut pas deviner : la permission d’écouter.

---

## Écran 0 — Pré-vol silencieux (hôte, invisible)
**Ce qu’on voit :** rien. La fenêtre n’apparaît pas encore.  
**Ce qu’on entend :** rien.  
**Ce qu’on peut faire :** rien. L’utilisateur vient de double-cliquer.  
**Comment on en sort :** automatiquement, après 1,2 s maximum.

L’agent hôte exécute, en série et sans blocage :
- `docker info` (démon présent ?)
- `nvidia-smi --query-gpu=memory.total` (VRAM ≥ 8 Go ?)
- `Get-PSDrive C` (espace libre ≥ 12 Go ?)
- `Invoke-WebRequest https://huggingface.co -Method Head -TimeoutSec 5` (route sortante ?)

Les résultats déterminent le parcours. Si Docker est absent, on ne montre jamais l’écran de bienvenue standard : on bascule direct sur l’écran Docker dégradé. Si le réseau est mort ou < 1,5 Mo/s, on arme le bouton *Mode démonstration* de l’écran 2.

**Sortie par échec :** si `docker` est introuvable, on affiche immédiatement l’écran 1-D (Docker requis). Si le disque est plein, on affiche un message bloquant clair.

---

## Écran 1 — Le Seuil
**Ce qu’on voit :**  
Fenêtre 900 × 600, fond `#0B0D10`. Au centre, un logo minimaliste : une ligne de waveform plate, gris ardoise. Titre en 24 px, police `Segoe UI Light` : « hyper-ambient ». Sous-titre en 13 px, gris `#8A8F98` :  
« Présence locale. Aucune donnée ne quitte cet ordinateur. »  
Un seul bouton pleine largeur (400 px) en bas : « Commencer », fond `#1F6FEB`, texte blanc.

**Ce qu’on entend :** rien. Le silence est assume : elle ne peut pas encore parler.

**Ce qu’on peut faire :** cliquer « Commencer », ou fermer la fenêtre (croix). Aucun champ, aucun réglage.

**Comment on en sort :** clic sur « Commencer » → écran 2. Fermeture → l’application quitte.

**Version dégradée :**  
- **Docker absent :** le sous-titre devient « Docker Desktop est requis pour faire tourner le cœur. » Le bouton devient « Installer Docker Desktop » (ouvre le `.exe` bundlé dans le dossier d’installation, ou le Microsoft Store). On n’essaie pas de cacher la dépendance ; on la traite comme un prérequis honnête.  
- **GPU absent ou < 8 Go :** une ligne rouge discrète apparaît : « Mode CPU détecté. Les réponses prendront ~10× plus de temps. » Le bouton reste « Commencer ».

---

## Écran 2 — La Chambre de gestation
**Ce qu’on voit :**  
La fenêtre s’agrandit à 1000 × 700. Le logo waveform se met à respirer (opacité 0,3 → 1,0, cycle 4 s).  
Trois phases s’affichent en colonne verticale à gauche, une seule active à la fois :
1. **Téléchargement** — barre de progression fine, texte exact : « Whisper large-v3 — 1,24 Go / 3,09 Go — 14 Mo/s » puis « Granite 3B — 0,80 Go / 2,00 Go ».
2. **Intégration** — cercle spinner, texte : « Extraction des poids dans le volume Docker ».
3. **Allocation GPU** — barre de VRAM, texte : « Réservation des 8 Go de VRAM — CUDA context ».

À droite, un panneau « Ce qui se passe » avec trois lignes dépliables (fermées par défaut) :
- « Pourquoi local ? »
- « Comment j’entends ? »
- « Comment je parle ? »

En bas à gauche : « Annuler » (lien texte gris).

**Ce qu’on entend :** un souffle très bas, sinusoïde 40 Hz à −45 dB, pour signaler que la machine travaille. Ce n’est pas sa voix. Le son s’arrête net au moment où les modèles sont prêts.

**Ce qu’on peut faire :** déplier les cartes, annuler. Le bouton « Commencer » de l’écran précédent a disparu ; il n’y a plus de retour en arrière.

**Comment on en sort :**  
- Succès : quand les trois phases sont vertes, l’écran 3 s’affiche automatiquement après 300 ms.  
- Échec disque/réseau : un encart rouge remplace la phase en cours avec le message exact (« Échec du téléchargement de Whisper — connexion interrompue ») et deux boutons : « Réessayer » et « Mode démonstration ».

**Version dégradée :**  
- **Réseau lent ou absent :** après 15 s sans progression, un bouton apparaît en bas à droite : « Mode démonstration ». En mode démo, les trois phases défilent en 4 s avec la mention « Simulation accélérée » et un bandeau permanent en haut de fenêtre : « MODE DÉMONSTRATION — Modèles non chargés ».  
- **CPU-only :** la phase 3 affiche « Allocation CPU — lent » et le panneau droit propose par défaut la carte « Pourquoi local ? » pour occuper l’attente.

**Ce qu’on fait d’utile pendant l’attente :** on ne demande aucune configuration. On pré-synthétise en arrière-plan, dès que le TTS est chargé, les trois phrases de l’écran 3 dans un cache WAV. Ainsi, la première voix sera instantanée, sans latence de génération.

---

## Écran 3 — La Naissance (le basculement voix)
**Ce qu’on voit :**  
La fenêtre rétrécit à 640 × 420. Le waveform devient cyan et pulse au rythme de la respiration. Un texte apparaît en 18 px : « hyper-ambient est prête. »  
Puis, en karaoké, les mots de sa première phrase s’affichent au centre, en sync avec l’audio.

**Ce qu’on entend :**  
Phrase 1 (voix féminine douce, posée, débit 0,95×) :  
« Bonjour. Je suis hyper-ambient. Je tourne entièrement sur cet ordinateur. Aucun son ne la quitte. »  
Phrase 2 :  
« Pour que je puisse vous entendre, j’ai besoin de votre permission. »  
À la fin de la phrase 2, un bouton pulse : « Autoriser le micro ».

C’est le moment précis du basculement clic → voix. Sa première parole n’est pas une démonstration technique : c’est une demande. La voix crée le besoin de la permission.

**Ce qu’on peut faire :** cliquer « Autoriser le micro ». Rien d’autre.

**Comment on en sort :** clic → écran 4. Si l’utilisateur ferme la fenêtre, l’app meurt.

**Version dégradée :**  
- **TTS indisponible (échec de chargement du modèle vocal) :** on utilise le TTS système Windows (SAPI 5, voix Hortense) avec une mention discrète en bas : « Voix système — mode dégradé ». Les phrases sont identiques.  
- **Mode démonstration :** on joue un WAV pré-enregistré (`first_voice.wav`, généré en développement avec le vrai moteur). Le bandeau « MODE DÉMONSTRATION » reste visible.

---

## Écran 4 — Le Lien (permission micro)
**Ce qu’on voit :**  
Au clic, l’agent hôte exécute `start ms-settings:privacy-microphone`. La fenêtre Tkinter passe en arrière-plan mais reste visible, réduite à un bandeau :  
« En attente de votre réponse dans la fenêtre Windows… »  
Un bouton « Annuler » apparaît après 20 s.

**Ce qu’on entend :** rien. Le silence laisse la place au dialogue système.

**Ce qu’on peut faire :** accorder ou refuser dans Windows, ou annuler.

**Comment on en sort :**  
- **Accordé :** le bandeau redevient la fenêtre normale. Une icône « oreille » apparaît, cyan. Texte : « Micro autorisé. » Puis transition auto vers écran 5.  
- **Refusé :** la fenêtre reprend le premier plan. Bandeau rouge : « Micro refusé. » Trois étapes numérotées avec captures d’écran embarquées :  
  1. Ouvrir Paramètres → Confidentialité → Microphone.  
  2. Activer « Autoriser les applications de bureau à accéder au microphone ».  
  3. Revenir ici.  
  Deux boutons : « Réessayer » (relance `ms-settings`) et « Continuer au clavier ».

**Version dégradée :**  
- **L’utilisateur ignore la fenêtre Windows et ne revient pas :** au bout de 30 s, le bouton « Annuler » clignote. Un clic ramène à l’écran 3 avec le texte « Permission non accordée. » et les deux boutons « Réessayer » / « Mode texte ».  
- **Continuer au clavier :** l’app bascule en mode texte définitif. Une barre de saisie remplace l’oreille. Un bandeau permanent en haut : « Micro coupé — Activer ». Ce n’est jamais un cul-de-sac : le produit fonctionne, la promesse vocale est différée.

---

## Écran 5 — Le Contrôle (introduction du mains libres)
**Ce qu’on voit :**  
Fenêtre 700 × 500. Au centre, une grande icône oreille, grise. Texte :  
« Je peux rester à l’écoute en continu. Ce voyant vous montre quand je vous entends. »  
Bouton principal : « Activer l’écoute continue ».  
Lien secondaire en bas : « Je préfère appuyer pour parler ».

Au clic sur « Activer », l’oreille devient cyan et pulse. Un nouvel élément apparaît, massif, en bas : un bouton rouge `#D13438`, 300 px de large, texte blanc 16 px : « COUPER LE MICRO ».  
Juste au-dessus, en petit : « Un double-clic sur l’icône de la zone de notification coupe aussi le micro. »

Puis une invite : « Dites quelque chose. » Un cadre de transcription apparaît.

**Ce qu’on entend :**  
Dès l’activation de l’écoute, elle dit : « Je vous écoute. »  
Après la première phrase détectée par Whisper, elle répond : « Je vous ai entendu. Vous gardez le contrôle. »

**Ce qu’on peut faire :** parler, cliquer « Couper », double-cliquer le tray, ou choisir le mode push-to-talk.

**Comment on en sort :**  
- Après le test micro, un bouton « Terminer » apparaît. Clic → écran 6 (ou 7 si pas de harnais).  
- Si l’utilisateur choisit « Je préfère appuyer pour parler », on saute à un écran minimal : « Maintenez Ctrl + Alt + Espace pour parler. » Puis « Terminer ».

**Version dégradée :**  
- **STT pas encore stable ou mode démo :** le test de transcription est remplacé par une animation de 3 s (barres qui bougent) puis un texte apparaît : « Transcription simulée : “bonjour” ». Le bandeau démo reste.  
- **Push-to-talk :** si l’utilisateur refuse l’écoute continue, on n’insiste pas. L’oreille reste grise, le bouton rouge est remplacé par « Raccourci : Ctrl+Alt+Espace ».  
- **Échec du kill switch (si l’utilisateur ne comprend pas) :** au bout de 10 s sans interaction, une infobulle pointe le bouton rouge : « Cliquez ici pour couper. »

---

## Écran 6 — L’Atelier (découverte des harnais)
**Ce qu’on voit :**  
Uniquement si `codex --version` ou `claude --version` répondent dans le `PATH` système.  
Fenêtre 600 × 400. Texte : « J’ai détecté Codex sur votre machine. »  
Case à cocher (cochée par défaut) : « Autoriser hyper-ambient à déléguer du code. »  
Phrase rassurante : « Vos projets restent locaux. »  
Bouton : « Continuer ».

**Ce qu’on entend :** rien. Cet écran est fonctionnel, pas conversationnel.

**Ce qu’on peut faire :** décocher, continuer.

**Comment on en sort :** clic « Continuer » → écran 7.

**Version dégradée :**  
- **Aucun harnais détecté :** l’écran est purement et simplement ignoré. On ne demande jamais d’installer Codex ou Claude Code.  
- **Détection échouée (erreur PATH) :** un lien discret « Configurer plus tard » mène directement à l’écran 7.

---

## Écran 7 — L’Éveil
**Ce qu’on voit :**  
La fenêtre fond en transparence (0,8 s). Une petite orbe apparaît dans la zone de notification (system tray), à côté de l’horloge. Au survol : « hyper-ambient — prête. Clic droit pour couper. »  
Si un harnais est actif, l’orbe a un petit point vert.

**Ce qu’on entend :**  
Dernière phrase, voix posée : « Je suis là. Appelez-moi quand vous voulez. »

**Ce qu’on peut faire :** double-cliquer l’orbe pour ouvrir une mini-fenêtre de chat ; clic droit pour « Couper le micro » ou « Quitter ».

**Comment on en sort :** la fenêtre d’onboarding est fermée. Le produit vit.

**Version dégradée :**  
- **Mode texte :** l’orbe est grise, l’infobulle indique « Mode texte ». Elle ne parle pas.  
- **Mode démonstration :** l’orbe porte un petit badge « D ». Au clic droit, une entrée « Quitter la démonstration » est ajoutée.

---

## Ce qu’on NE demande PAS au premier lancement

| Question évitée | Raison |
|---|---|
| Choix du mot d’activation | Elle s’appelle *hyper-ambient*. Le nom EST le déclencheur implicite ; on n’ajoute pas de friction. |
| Choix de la voix | Une seule voix féminine, douce et posée. C’est l’identité. |
| Choix du modèle (large-v3 vs medium) | Un seul modèle. La VRAM de 8 Go est calibrée pour large-v3 + Granite 3B. |
| Clé API, token, compte | Produit local. Zéro compte. |
| Dossier de travail | Par défaut `%USERPROFILE%\hyper-ambient\workspace`. Modifiable plus tard. |
| Sensibilité du micro | Calibrée silencieusement pendant l’écran 5 (mesure du bruit de fond). |
| Opt-in télémétrie | Aucune télémétrie. On ne pose pas la question. |
| Configuration GPU | Détection automatique via `nvidia-smi`. |

---

## Mode démonstration (protocole jury)

**Déclenchement :** à l’écran 2, après 5 secondes, si le test de débit vers `huggingface.co` est < 1,5 Mo/s ou échoue, le bouton « Mode démonstration » devient visible.

**Ce qui change :**
- Un bandeau rouge permanant, en haut de chaque écran : « MODE DÉMONSTRATION — Modèles non chargés ».
- L’écran 2 est compressé à 4 s avec la mention « Simulation accélérée ».
- L’écran 3 joue un WAV pré-enregistré (`first_voice.wav`). La voix est la vraie, capturée en développement.
- L’écran 4 (permission micro Windows) est **réel** : le jury voit le dialogue OS natif.
- L’écran 5 affiche les vrais états de l’interface (oreille, bouton rouge), mais la transcription est scriptée et étiquetée « simulée ».
- L’écran 6 (détection harnais) est **réel** : `codex --version` s’exécute vraiment.
- L’écran 7 reste identique.

**Pourquoi ce n’est pas une triche :** le bandeau ne disparaît jamais. Les interactions OS (permission, boutons, tray) sont authentiques. Ce qui est simulé est uniquement le cœur neuronal, et c’est annoncé.

---

## Ce qu’on coupe si le temps manque (ordre de sacrifice)

1. **Les cartes pédagogiques de l’écran 2.** Remplacer par une ligne : « Téléchargement des modèles locaux… ».
2. **L’écran 6 (harnais).** Détecter en arrière-plan après l’onboarding ; ne jamais bloquer le parcours.
3. **Le test de transcription en direct de l’écran 5.** Garder uniquement l’oreille et le bouton rouge « Couper ».
4. **Le tutoriel écoute continue.** Après la naissance, ouvrir directement le tray avec une infobulle : « Je vous écoute. Clic droit pour couper. ».
5. **La voix entièrement.** Si le TTS met > 90 s à charger, basculer en mode texte dès l’écran 3. Une assistante vocale muette au premier lancement est un échec ; une assistante texte locale est un produit.

---

## Les cinq décisions que seul le fondateur peut trancher

**1. L’écoute continue doit-elle s’activer automatiquement dès que la permission micro est accordée, ou rester désactivée jusqu’à un geste explicite supplémentaire ?**  
**Recommandation :** activation automatique. C’est la promesse produit. Mais avec un voyant clignotant pendant 60 s et le bouton « Couper » ancré en haut de la fenêtre principale.

**2. Faut-il livrer un installateur « jury » de ~8 Go contenant les modèles pré-téléchargés, ou compter sur le réseau de la salle ?**  
**Recommandation :** livrer l’installateur offline avec modèles pré-cachés. Un jury ne pardonne pas une barre de progression bloquée à 40 %.

**3. Docker Desktop doit-il être un prérequis installé par notre `.exe`, ou l’application doit-elle refuser de démarrer s’il est absent ?**  
**Recommandation :** l’installateur vérifie et propose l’installation de Docker Desktop en un clic, mais le dossier du jury doit être préparé avec Docker déjà actif et le volume vidé.

**4. En cas de refus de permission micro, l’application doit-elle proposer immédiatement le mode texte, ou insister avec un guide visuel ?**  
**Recommandation :** proposer le mode texte immédiatement, avec un bandeau permanent « Micro coupé — Activer ». Ne jamais bloquer sur un écran de réessai.

**5. Le mode démonstration doit-il réutiliser l’interface réelle avec un bandeau « DEMO », ou basculer sur une vidéo pré-enregistrée en plein écran ?**  
**Recommandation :** réutiliser l’interface réelle avec bandeau DEMO et audio pré-enregistré. Une vidéo casse l’illusion de produit vivant et fait perdre le contrôle du clavier.