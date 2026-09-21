# Nuit A — chemin écrit, transcriptions relisibles, hallucinations d'EARS

Bonjour, je suis Opus et je travaille pour Human IA. Le fondateur dort, on boucle la
nuit. Tu es **seul propriétaire** de `dev/scripts/serve_hostagent.py` cette nuit :
d'autres agents travaillent en parallèle sur d'autres fichiers, ne sors pas de ton
périmètre.

## État acquis — ne le refais pas, ne le remets pas en cause

Le routeur est désormais actif (`dev/scripts/carte_figee.env` : `BRAIN_SERVICE=router`,
`BRAIN_MODEL=MiniMaxAI/MiniMax-M3`). Mesure de bout en bout que je viens d'exécuter dans
le conteneur, sur la vraie chaîne :

    BRAIN: router
    « Bonjour, comment vas-tu ? »            -> 650 ms, canal reflex (local), aucun outil
    « Demande a Codex de lister les .py... » -> 2209 ms, canaux deep+filler+tool,
                                                ask_codex appelé, MANDAT déposé

La spécification est donc respectée : le local tient le temps réel, le distant pilote les
harnais. **Ne touche pas à `carte_figee.env`.**

## Tâche 1 — retirer le forçage `tool_choice`

Tu as ajouté hier un `tool_choice` forcé quand le prompt nomme un harnais. Il visait à
contraindre le modèle **local**, qui refusait d'appeler `ask_codex`. Ce n'était pas le bon
correctif : le fondateur a tranché, « c'est censé être le modèle distant qui gère la
connexion avec les harnais locaux, le modèle local est à la rue sur ce genre de trucs ».
La mesure ci-dessus le confirme — le distant appelle l'outil **de lui-même**, sans forçage.

Retire donc le câblage du forçage côté `serve_hostagent.py` et les tests qui le couvrent.
**Garde** en revanche le paramètre `tool_choice` de `run_tool_loop` dans
`src/brain/tool_loop.py` avec ses tests : l'API est correcte et sert d'échappatoire, elle
n'est simplement plus câblée par défaut. Garde aussi le court-circuit `nomme_un_harnais`
de `src/brain/router.py` : c'est lui qui fait escalader.

Raison de retirer le câblage : forcé, « qu'est-ce que Codex ? » déclencherait un appel
d'outil au lieu d'une réponse.

## Tâche 2 — un chemin ÉCRIT dans le produit

Consigne littérale du fondateur : « vous devez tester la fluidité de l'appli avec les
harnais, vous n'avez pas besoin de la voix, juste du modèle local et distant. L'idée c'est
de pouvoir se servir de ces harnais correctement à la voix. Donc il faut de l'écrit aussi. »

Il demande deux choses à la fois : un moyen de **tester** sans micro, et une **entrée
texte dans le produit**. Fais les deux :

- `dev/scripts/parler_ecrit.py` : une boucle interactive qui monte exactement le même
  pipeline que le tour vocal (routeur, registre d'outils, porte, registre de mandats,
  veille des mandats) mais lit stdin et écrit stdout. Pas de EARS, pas de MOUTH, pas de
  websocket. Elle doit afficher le canal utilisé (reflex / deep), la durée, les appels
  d'outil, les mandats déposés et leur réponse quand elle arrive. C'est l'outil avec
  lequel on validera la fluidité des harnais cette nuit. Prévois un mode non interactif
  (une question passée en argument) pour pouvoir la scripter.
- Réutilise le code existant plutôt que de le recopier : si le montage du pipeline est
  enfermé dans la classe du serveur, extrais-en une fonction de construction et appelle-la
  des deux côtés. Un second montage divergent serait une dette immédiate.

## Tâche 3 — transcriptions relisibles hors ligne

Consigne littérale : « l'utilisateur doit pouvoir retrouver facilement la transcription de
la convo. Il faut que ça écrive dans un répertoire les convos et qu'on puisse les relire
après (juste en local) ».

- Un fichier par conversation, en Markdown, horodaté, par exemple
  `%LOCALAPPDATA%\hyper-ambient\conversations\2026-09-21_23-42.md` côté hôte. Le
  host-agent tourne en conteneur : écris via un chemin monté, et **vérifie par lecture
  réelle du fichier depuis l'hôte** qu'il arrive au bon endroit. Ne présume pas du chemin ;
  regarde comment les journaux existants s'y prennent.
- Contenu : l'heure, qui parle, le texte. Les appels d'outil et les mandats y figurent en
  une ligne (`→ Codex : <question>` / `← Codex : <résumé>`). Lisible par un humain dans
  un éditeur de texte, sans outil.
- **Aucune donnée ne sort de la machine.** Ce fichier est local, et il devra être
  mentionné dans `DONNEES.md` et `DONNEES.en.md` — signale-le dans ton compte rendu,
  quelqu'un d'autre tient ces fichiers, ne les édite pas toi-même.
- Écriture incrémentale (à chaque tour), pas en fin de session : une coupure ne doit pas
  perdre la conversation.

## Tâche 4 — EARS hallucine sur le bruit, et c'est ça qui l'a réveillée

Fait mesuré cette nuit. Le fondateur était en mains libres, il ne parlait pas, une moto
est passée dans la rue, et elle a répondu « je t'écoute ». Journal du host-agent :

    C10 t=182751.744 TRANSCRIPT "Sous-titrage ST' 501" ears_ms=627
    C10 t=182894.135 TRANSCRIPT 'Sous-titrage FR ?'    ears_ms=541
    JEV   : harnais nommé (observation, aucun envoi)
    JEV   : interpellation sans demande — reveil court

**JeV n'est pas le coupable** : il a jugé correctement un texte qui n'aurait jamais dû lui
parvenir. « Sous-titrage FR ? » est une hallucination classique de faster-whisper sur du
bruit non vocal — la famille « Sous-titrage », « Sous-titres réalisés par la communauté
d'Amara.org », « Merci d'avoir regardé cette vidéo », « ♪ ». Le modèle a été entraîné sur
des sous-titres et produit ces phrases quand l'audio ne contient pas de parole.

Correctif demandé, dans l'ordre de préférence :

1. **Le signal du modèle d'abord.** faster-whisper expose par segment
   `no_speech_prob` et `avg_logprob`. Un segment au-dessus du seuil de non-parole, ou au
   log-prob trop bas, doit être jeté avant d'atteindre JeV. C'est la défense générale,
   elle ne dépend d'aucune liste. Vérifie ce que le code expose déjà avant d'ajouter quoi
   que ce soit ; si ces champs ne remontent pas jusqu'au tour, fais-les remonter.
2. **Une liste de garde en complément**, insensible à la casse et aux accents, sur le
   texte normalisé : « sous-titrage », « sous-titres réalisés par », « amara.org »,
   « merci d'avoir regardé », « abonnez-vous », et les versions anglaises
   « subtitles by », « thanks for watching ». Elle couvre le cas où les probabilités
   passent. Commente que cette liste est un filet, pas la défense principale.
3. Un tour ainsi jeté doit être **journalisé** (`EARS  : segment rejeté (bruit) "..."`)
   et ne doit ni ouvrir la fenêtre de conversation, ni réveiller, ni parler.

**Ce comportement n'existe qu'en mains libres** : sur un appui du bouton Parler,
l'utilisateur a décidé de parler, on ne jette rien.

## Tests

TDD, rouge d'abord. Les hallucinations connues sont rejetées, une phrase normale passe, un
segment à forte probabilité de non-parole est rejeté, et le rejet n'a pas lieu hors mains
libres. Pour les transcriptions : un tour écrit une ligne, deux tours en écrivent deux,
le fichier est relisible et ne contient aucun secret.

Colle la sortie de la suite complète :
`python -m pytest dev/tests -q`

## Contraintes

- Périmètre : `dev/scripts/serve_hostagent.py`, `dev/scripts/parler_ecrit.py`,
  `src/brain/tool_loop.py`, `native/hostagent/*` si EARS l'exige, et les tests associés.
  **Ne touche pas** à `carte_figee.env`, `.env.local`, `src/onboarding/`,
  `native/presence/reglages_ui.py`, `README.md`, `packaging/`, `DONNEES*.md` — d'autres
  agents les tiennent cette nuit.
- Aucune commande git : ni branche, ni commit, ni push. C'est mon périmètre.
- Ne révèle aucune valeur de clé API dans le code, les tests, les journaux ou ton rapport.
- Compte rendu dans `nights/2026-09-21-OUT-CURSOR-NUIT-A.md`, avec les sorties de commande.
