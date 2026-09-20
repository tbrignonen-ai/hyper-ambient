Tu es consulte comme architecte produit. Reponds en francais. NE LIS AUCUN
FICHIER du depot : tout le contexte utile est ci-dessous. Ecris ta reponse dans
`nights/2026-09-20-OUT-FABLE-HARNAIS.md` et ne reponds que OK.

# Le produit
`hyper-ambient` : une presence vocale ambiante sur un PC Windows. Voix feminine,
calme. L'utilisateur lui parle, elle repond a voix haute. Elle tourne en local
(Granite 4.2 3B, Whisper, TTS local), latence cible ~1,2 s du micro au premier
son. Deux modes : appuyer-pour-parler, et mains libres (micro ouvert, un filtre
decide si on lui parle, puis une fenetre de conversation de 30 s).

Son originalite revendiquee : elle sait declencher les HARNAIS DE CODE deja
installes sur la machine — Claude Code et Codex (CLI, joints par un pont HTTP
local). L'utilisateur peut lui dire « demande a Codex de regarder ce fichier ».

# Le probleme a trancher
Un harnais rend du TEXTE LONG : un diagnostic, un diff, une liste de fichiers,
parfois plusieurs milliers de caracteres. Or :
- une voix ne peut pas lire cela, ce serait interminable et inutilisable ;
- l'appel prend 20 a 60 secondes, parfois davantage ;
- un appel a deja bloque le produit 39 secondes en silence total, en pleine
  conversation. L'utilisateur a cru que le mode avait plante.

Contraintes acquises, ne les rediscute pas :
- Perimetre : Claude Code et Codex uniquement.
- Elle ne doit JAMAIS appeler un harnais sans demande explicite de l'utilisateur.
- Le modele distant qui pilote le harnais peut raisonner longuement et disposer
  de beaucoup de contexte ; il peut donc produire un RESUME TRES COURT destine a
  la voix, en plus du resultat complet.
- Pour du gros volume, l'utilisateur travaillera de toute facon directement dans
  Codex ou Claude Code. Le produit n'a pas a rivaliser avec leur interface.

# Tes questions, dans l'ordre d'importance
1. Quelle est la BONNE FORME de l'echange, du point de vue de l'utilisateur ?
   Que dit-elle pendant l'attente ? Que dit-elle a l'arrivee du resultat ?
   Que fait-on du texte long ?
2. Faut-il FAIRE APPARAITRE la fenetre du harnais (Codex / Claude Code) au
   premier plan quand le resultat arrive ? Toujours, jamais, sous condition ?
   Si sous condition, laquelle, et qui decide — elle, ou l'utilisateur ?
   Si on la fait apparaitre, a quel MOMENT exactement (a l'envoi ? a l'arrivee ?
   a la demande de l'utilisateur ?), et que devient la conversation vocale
   pendant ce temps ?
3. Faut-il demander son avis a l'utilisateur au moment de la demande (« je te
   l'ouvre quand c'est pret ? »), ou est-ce une friction de trop dans une
   interface vocale ?
4. Un appel qui prend 40 s dans une conversation ou les tours durent 2 s : comment
   ne pas casser le fil ? Peut-elle continuer a parler pendant ? Que se passe-t-il
   si l'utilisateur lui parle d'autre chose entre-temps ?
5. Un SEUIL DE CONFIANCE avant de declencher un harnais a-t-il du sens, ou est-ce
   une fausse bonne idee ? Argumente.

# Format attendu
Pour chaque question : une recommandation TRANCHEE, puis deux ou trois phrases de
justification, puis ce qu'elle coute. Pas de liste d'options sans choix. Si tu
estimes qu'une de mes questions est mal posee, dis-le et repose-la.
Sois dense. Pas de preambule, pas de resume final.
