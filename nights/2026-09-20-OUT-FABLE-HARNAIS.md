# Réponse — forme de l'échange avec les harnais (Claude Code, Codex)

## 1. La bonne forme : un MANDAT asynchrone, jamais un tour de parole

**Recommandation.** L'appel au harnais n'est pas une réponse, c'est un mandat confié. Trois temps, chacun d'une phrase :

- **Accusé immédiat (< 1 s, avant toute latence réseau)** : « Je demande à Codex de relire transport.py. Je te préviens. » Elle reformule le mandat en une proposition, puis rend la main. Rien d'autre. Pas de « patiente », pas de remplissage, pas de son d'attente.
- **Pendant** : silence total sur le sujet, sauf si l'utilisateur demande où ça en est (« pas encore, ça fait vingt secondes »). Un seul rappel spontané, à 60 s, uniquement si la conversation est silencieuse : « Codex prend du temps, je te préviens dès que c'est prêt. »
- **À l'arrivée** : « Codex a fini. » + un résumé vocal de deux phrases maximum (≈ 220 caractères, ≈ 12 s de TTS), écrit **par le modèle distant**, pas par le Granite 3B local. Le résumé est suivi d'une seule offre, un mot : « Tu veux le détail, ou que je te l'ouvre ? »

**Le texte long n'est jamais lu.** Il existe déjà là où il doit être : dans la session Codex / Claude Code. Le produit ne transporte que le résumé et un pointeur. Si l'utilisateur dit « le détail », elle lit un deuxième niveau (trois à cinq phrases, également préparé par le distant), et s'arrête là définitivement. Le troisième niveau, c'est la fenêtre du harnais.

**Contrat de sortie imposé au harnais** (via le prompt système du pont) : `verdict` (fait / à vérifier / échec), `resume_voix` (≤ 220 car., phrases complètes, zéro chemin de fichier, zéro identifiant), `detail_voix` (≤ 600 car.), `resultat_complet` (libre). Le local ne parse jamais du texte libre ; s'il manque `resume_voix`, elle dit « Codex a répondu mais je n'ai pas de résumé, je te l'ouvre ? ».

**Justification.** Le distant a le contexte et le temps de raisonner ; c'est le seul endroit où la compression est fiable. Le local 3B résumant 5 000 caractères de diff produirait des contresens à voix haute, ce qui est pire que le silence. Le découpage en niveaux transforme un mur de texte en une conversation à débit humain.

**Coût.** Un shim de prompt système par harnais avec schéma strict et validation ; une machine à états « mandats » (id, harnais, énoncé, t0, statut, résultat) dans la présence ; le TTS doit savoir interrompre son planning pour insérer l'annonce (voir 4).

## 2. Faire apparaître la fenêtre : jamais automatiquement

**Recommandation.** Elle ne prend **jamais** le premier plan d'elle-même, ni à l'envoi, ni à l'arrivée. Elle l'ouvre uniquement sur demande explicite (« ouvre », « montre-moi ») — soit dans le mandat initial (« ouvre Codex et demande-lui… »), soit en réponse à l'offre d'arrivée. Le moment est donc toujours : **quand l'utilisateur le dit**. Entre-temps, un signal visuel passif suffit : un point ou un badge sur son overlay (« 1 résultat prêt »), qui disparaît quand le mandat est consommé.

Pendant que la fenêtre est au premier plan, la conversation vocale **ne change pas d'état** : la fenêtre est un pair, pas un mode. Si l'utilisateur lui parle, elle répond ; si la fenêtre est fermée ou perd le focus, rien ne se passe côté voix.

**Justification.** Voler le focus est la faute capitale d'un logiciel ambiant : l'utilisateur tape peut-être ailleurs, est en visio, ou a lancé le mandat précisément pour ne pas avoir à regarder. La proposition de valeur, c'est « je n'ai pas besoin d'aller voir » ; une fenêtre qui surgit dit le contraire. Et l'utilisateur qui veut le gros volume ira dans Codex de lui-même, c'est acquis.

**Coût.** Windows refuse `SetForegroundWindow` depuis un processus qui n'a pas le focus ; il faut soit passer par l'hôte natif qui détient déjà l'input (le hostagent), soit se contenter d'un clignotement de barre des tâches (`FlashWindowEx`) comme repli. Il faut aussi retrouver la bonne fenêtre (titre / PID du CLI lancé par le pont), donc le pont doit conserver le PID de session.

## 3. Demander « je te l'ouvre quand c'est prêt ? » à la demande : non

**Recommandation.** Ne jamais poser la question au moment de la demande. Décision par défaut : ne pas ouvrir, offrir une fois à l'arrivée (un mot, collé au résumé, cf. 1). Honorer l'intention si elle est déjà dans la phrase (« ouvre Codex et… »).

**Justification.** La réponse est prévisible dans 90 % des cas et l'utilisateur ne sait pas encore, au moment de la demande, si le résultat méritera d'être regardé ; c'est à l'arrivée qu'il le sait. Une question dont la réponse est « on verra » coûte un tour entier de parole (≈ 4 s aller-retour) pour rien, et casse le rythme de 2 s qui fait la qualité du produit.

**Coût.** Quasi nul : une règle d'extraction d'intention (verbes d'ouverture) dans le mandat, et l'offre en fin d'annonce.

## 4. 40 s dans une conversation à 2 s : fire-and-forget, et interjection au silence

**Recommandation.** L'appel part dans un worker de fond dès l'accusé ; la boucle de tours **rend la main immédiatement**. Le blocage de 39 s est un défaut d'architecture (appel synchrone dans le tour), pas un problème d'UX à habiller : il ne se corrige pas avec du remplissage vocal, il se corrige en sortant l'appel du tour.

Règles :
- L'utilisateur parle d'autre chose : elle répond normalement, le mandat reste en cours, le contexte de conversation garde une ligne « mandat #3 Codex en cours depuis 25 s » pour qu'elle puisse en parler si on lui demande.
- Le résultat arrive pendant qu'elle parle ou que l'utilisateur parle : elle **attend la fin du tour** puis un blanc d'≈ 1,5 s, et interjecte avec un marqueur : « Au fait — Codex a fini. » Jamais d'interruption au milieu d'une phrase, dans un sens ou l'autre.
- Mains libres : un mandat en cours garde la fenêtre de conversation armée jusqu'à la livraison, et la livraison ouvre une fenêtre courte (≈ 10 s) pour « le détail » / « ouvre » sans mot de réveil. Elle ne rouvre pas les 30 s pleines.
- Timeouts : rappel unique à 60 s (si silence), abandon à 180 s : « Codex n'a pas répondu, j'arrête d'attendre ; la fenêtre est toujours là. »
- Concurrence : un mandat à la fois par harnais, deux au total. Au-delà : « J'attends que Codex finisse d'abord. »

**Justification.** Une conversation supporte très bien qu'un tiers « revienne » avec une nouvelle, c'est un schéma social connu (« au fait, à propos de… ») ; elle ne supporte pas le silence inexpliqué. Le marqueur d'interjection est ce qui permet au cerveau de changer de sujet sans perdre le fil précédent.

**Coût.** Une file de mandats avec identifiants et statut ; un planificateur TTS capable d'insérer une annonce entre deux tours (détection de fin de parole côté utilisateur incluse) ; injection d'une ligne d'état dans le prompt local à chaque tour tant qu'un mandat est ouvert ; deux minuteurs par mandat.

## 5. Seuil de confiance : fausse bonne idée, question mal posée

**Recommandation.** Pas de seuil numérique. Les probabilités d'un modèle 3B en appel d'outil ne sont pas calibrées ; un seuil à 0,7 ne mesure rien et donnera des refus inexplicables un jour, des déclenchements aberrants le lendemain. La question réelle est double et se tranche autrement :

**a) Intention : une porte lexicale, pas une confiance.** L'outil « harnais » n'est **exposé** au modèle local que si le transcrit contient le nom d'un harnais (Codex, Claude) ou un verbe d'une liste fermée (« demande à », « fais regarder par », « lance »), en français et en anglais. Sinon l'outil n'existe pas dans ce tour et le modèle ne peut pas l'halluciner. C'est déterministe, testable, et ça honore la contrainte « jamais sans demande explicite » mieux que n'importe quel score.

**b) Risque : une porte par réversibilité, pas par confiance.** Le vrai danger n'est pas de mal comprendre « regarde ce fichier », c'est de déclencher « corrige ce fichier » à tort : Codex écrit sur le disque. Donc :
- mandat en lecture (regarder, analyser, expliquer, lister) → départ immédiat, l'accusé reformulé sert de confirmation implicite ; l'utilisateur peut dire « non » dans les 2 s et elle annule ;
- mandat en écriture (corrige, modifie, refactorise, supprime) → confirmation explicite obligatoire : « Je lui demande de **modifier** transport.py ? » ; et le harnais est lancé en mode sandbox lecture seule par défaut (`--sandbox read-only` / mode plan), l'écriture n'étant autorisée qu'après ce « oui ».

**Justification.** Un seuil déplace la décision vers une grandeur que personne ne peut ni expliquer ni régler ; une porte lexicale et une porte de réversibilité sont deux règles qu'on peut dire à voix haute à l'utilisateur, et c'est le critère d'un produit vocal. Le coût d'un faux positif en lecture est 40 s et quelques tokens, tolérable ; en écriture c'est un fichier modifié, intolérable sans « oui ».

**Coût.** Deux listes de déclencheurs FR/EN à maintenir et tester ; un classement lecture/écriture des verbes (le doute est classé écriture) ; un tour supplémentaire uniquement pour les mandats en écriture ; le pont doit savoir lancer les deux harnais en mode lecture seule et repasser en écriture sur autorisation.
