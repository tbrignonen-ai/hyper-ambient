# Brief — Interruption a la voix en mains libres, et Stop qui ne tue plus le mode

Bonjour, je suis Opus et je travaille pour Human IA. Merci d'avance.

Deux defauts rapportes par le fondateur apres un test reel ce soir. Le mode mains
libres se declenche bien et enchaine les tours — ce n'est pas la detection qui est
en cause.

## Defaut 1 — On ne peut pas l'interrompre a la voix

**C'est le plus important.** En mains libres, quand elle part sur une reponse
longue, il faut pouvoir la couper **en parlant**, sans rien toucher. Aujourd'hui
c'est structurellement impossible :

- `native/presence/app.py`, `_expedier_tour_continu` : `capture.suspendre()` est
  appele juste avant la lecture, et la boucle `_boucle_tours` refait
  `capture.suspendre()` a chaque tick tant que `en_lecture` est arme.
- Le seul `interrompre` passe a `consommer_reponse` est `self.tenu`, c'est-a-dire
  **le bouton Parler**. Il n'y a aucun chemin vocal.

Le micro est donc volontairement sourd pendant qu'elle parle. C'etait l'anti-echo :
sans lui, elle s'entend elle-meme et se repond. Il faut remplacer « sourdine
totale » par « ecoute exigeante ».

### Ce qu'il faut construire

Pendant la lecture, **la capture reste active** mais entre dans un regime strict,
a ajouter dans `native/hostagent/windows_audio.py` :

- un seuil RMS releve — pars sur **2,5 fois** le seuil calibre, et rends le
  facteur reglable par une constante nommee (ex. `FACTEUR_SEUIL_LECTURE`) ;
- la verification de bande de voix humaine deja presente (`_trame_voix`,
  85–3400 Hz) reste exigee ;
- une duree minimale de voix continue plus longue qu'en temps normal — pars sur
  **400 ms** — avant de declarer une interruption. Un « euh » ou un raclement de
  gorge ne doit pas la couper.

Quand ces trois conditions sont reunies, c'est un barge-in vocal : on coupe la
voix (`sortie.abort()`), on **conserve** l'audio deja capte comme debut du tour
suivant (ne le jette pas : c'est le debut de sa phrase), et on enchaine
normalement.

Expose cela proprement, par exemple une methode `regime_lecture(actif: bool)` sur
la capture continue, plutot qu'en trafiquant `_suspendu` depuis l'exterieur.

Si l'echo se revele trop fort pour cette approche, **dis-le dans ton rapport
plutot que de bricoler** : la solution serait alors une annulation d'echo, et
c'est une decision d'architecture qui ne t'appartient pas.

## Defaut 2 — Stop tue le mode au lieu de couper la phrase

Ses mots exacts : *« si je fais stop en mode main libre active : ca ne doit pas
arreter le mode conversationnel actif du mode main libre, juste sa reponse. »*

Apres un Stop, il a constate qu'il etait **impossible de reprendre** alors que le
bouton restait visuellement actif. Le journal le confirme :

```
ML : segment 4 detecte (292 trames)
envoi : 292 trames
stop : coupure voix
tour : termine
ML : vivante, 4 segment(s) envoye(s), lecture=non, suspendue=non   (x6, soit 30 s)
```

Le tour se termine proprement, la capture se dit **non suspendue**, la boucle est
**vivante** — et pourtant aucun segment 5 n'arrive pendant trente secondes.

**Je n'ai pas la cause racine, et je ne veux pas que tu devines.** Trois pistes
que j'ai ecartees, pour t'eviter de refaire le chemin : la calibration du seuil
n'est faite qu'une fois et n'est pas reinitialisee par `reprendre()` ; le flux de
sortie se redemarre tout seul dans `_jouer` apres un `abort()` ; et
`couper_voix` ne touche pas a `mains_libres` (le `mains_libres=OFF` du journal
arrive trente secondes plus tard, c'est le fondateur qui a bascule le bouton
lui-meme pour tenter de recuperer).

### Ce que je te demande, dans cet ordre

1. **Instrumente d'abord.** Ajoute des traces qui permettront de trancher au
   prochain test entre : elle n'a pas entendu / elle a entendu mais n'a pas
   ferme le segment / elle a envoye mais rien n'est revenu. Concretement, dans
   le pouls `ML : vivante`, ajoute au minimum le seuil RMS courant, le RMS de la
   derniere trame vue, si un tour est en cours d'accumulation, et l'etat de
   `couper`. Sans ces chiffres on redebogue a l'aveugle.
2. **Garantis la semantique de Stop**, quelle que soit la cause : Stop coupe la
   phrase en cours et **rien d'autre**. Le mode mains libres reste actif, la
   fenetre de conversation reste ouverte, la capture reprend immediatement, et
   le tour suivant doit pouvoir partir. Verifie en particulier qu'un Stop
   presse **juste apres** la fin d'une lecture ne laisse pas `self.couper` arme
   pour le tour d'apres.
3. Si l'instrumentation te donne la cause racine en cours de route, corrige-la
   et dis-le. Sinon, livre l'instrumentation et la garantie de semantique.

## Perimetre

Tu peux modifier : `native/presence/app.py`, `native/hostagent/windows_audio.py`,
`dev/tests/test_presence_premier_tour.py`, et creer `dev/tests/test_barge_in.py`.

Interdits : `src/brain/mandat.py`, `src/brain/contrat_harnais.py`,
`src/ears/jev_reflexe.py`, `dev/scripts/serve_hostagent.py`. **Aucune commande
git** — Opus relit le diff et commite.

## Verification

`docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py`

Reference avant ton travail : **1313 passes, 5 echecs pre-existants**
(`test_c11_identity`, `test_presence_onboarding`, `test_presence_premier_tour`,
deux de `test_taquet_produit`). Aucun echec nouveau.

Compte rendu dans `nights/2026-09-20-OUT-CURSOR-BARGE-IN.md` : ce que tu as fait,
la sortie exacte de pytest, ce que tu n'as pas pu faire, et **ton verdict honnete
sur la faisabilite de l'anti-echo sans annulation d'echo**.
