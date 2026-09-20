---
date: 2026-09-20
type: audit-ecart
scope: native/presence onboarding
method: lecture statique des specifications, du code et des tests demandes
---

# Audit d'écart — onboarding hyper-ambient

## Verdict

Le wizard PTT minimal est réel et relativement propre : la préférence absente ou
invalide relance le parcours, le son ne démarre qu'après sa sortie, le raccourci
est persisté atomiquement, et les erreurs audio/serveur reviennent dans la ligne
d'état. En revanche, le produit actuellement livré est un wizard **PTT à quatre
étapes**, pas l'onboarding **LLM V1 à quatre preuves** demandé le 17 septembre.
Les écrans Déclarer, Guider, Armer et Essayer n'existent pas.

La soutenance sur une machine vierge peut terminer le wizard, mais ne peut pas
produire le « premier moment » : sans dépendances/modèle/service/micro, le canal
reste indisponible et le premier appui PTT affiche seulement une erreur. Il n'y a
ni diagnostic guidé, ni installation/configuration, ni solution de repli.

## Périmètre et lecture des sources

Sources lues intégralement : les six notes demandées, `onboarding.py`, les
sections onboarding/session/CLI de `app.py`, et
`dev/tests/test_presence_onboarding.py`. Aucun test n'a été exécuté : une
exécution de pytest peut écrire des caches, alors que cette mission autorise un
seul fichier en écriture.

Les sources portent deux niveaux de promesse contradictoires :

- Le design Codex du 14 septembre fixe volontairement une tranche PTT minimale
  (vidéo, hotkey Windows, tray et bascule hors périmètre).
- Muse décrit une cible vocale en six étapes ; le document LLM V1 du 17 septembre
  transforme une partie de cette cible en quatre étapes obligatoirement prouvées.

Les écarts ci-dessous distinguent donc un défaut de la tranche PTT d'un manque
explicite de LLM V1, plutôt que de présenter les décisions « hors périmètre » du
14 comme des bugs accidentels.

## Écarts constatés

| Écran / étape | Promesse des specs | Ce que le code fait réellement | Gravité |
|---|---|---|---|
| Parcours global | Design Codex : Bienvenue → choix PTT → conversation ; Cursor : trois étapes skippables. | `ETAPES_WIZARD` contient quatre étapes : `bienvenue`, `mains_libres`, `ptt`, `masquage`. L'écran mains libres, plus les choix langue et contraste à l'accueil, transforment les « deux/trois réglages » annoncés en quatre réglages. | Visible |
| Accueil / guide par le modèle (Muse 1–2) | Chargement local calme, puis bonjour parlé et sous-titré par le modèle, avec « Lire seulement ». | L'accueil est immédiatement statique ; aucun chargement de modèle, aucune voix/sous-titre de modèle, ni choix lecture seule. Cela est cohérent avec la tranche Codex qui veut pouvoir finir sans Hermes, mais non avec la cible Muse. | Visible |
| Étape « Mains libres » | Le design Codex impose une même sémantique PTT : maintien = écoute, relâchement = envoi ; le mode bascule était explicitement hors tranche. | « Activer » expose un mode où le premier appui démarre et le suivant envoie ; `relache_termine_lecoute()` renvoie faux. Le choix est désormais assumé par la note du 20 septembre, mais il reste un écart avec le contrat PTT du 14. | Visible |
| Fin du wizard / masquage (Muse 4 et 6) | La fenêtre se masque à la fin ; Muse annonce qu'elle disparaît automatiquement. | L'écran 4 propose deux issues : CTA principal « Commencer » (fenêtre laissée ouverte) et action secondaire « Commencer et masquer ». `iconify()` est correctement utilisé seulement dans la seconde issue. | Visible |
| Après masquage (Muse 6) | Rappel discret pendant 10 s : comment rappeler la configuration et rappel PTT. | Aucun minuteur ni rappel temporaire. La fenêtre ouverte affiche bien le raccourci et l'aide, mais rien n'apparaît après `iconify()`. | Cosmétique |
| Vidéo optionnelle (Muse 5) | Choix « Avec vidéo » / « Voix seule », voix seule par défaut, overlay persistant et masquable. | Aucun écran, aucune persistance ni orchestration vidéo. C'est explicitement hors périmètre de la tranche Codex/Cursor ; c'est néanmoins un écart avec la proposition Muse. | Visible — hors tranche assumée |
| LLM V1 — modèle d'état | `ETAPES_LLM`, un état de harnais avec cause, et une persistance `onboarding_llm` séparée de `onboarding_termine`. | `onboarding.py` ne contient que `ETAPES_WIZARD` et `ConfigurationPresence` PTT (raccourci/langue/contraste/mains libres). Aucun état LLM, aucun état par harnais, aucune reprise du parcours LLM. | Bloquant pour la démo LLM |
| LLM V1 — 1. Déclarer | Formulaire nom/URL/clé du distant, secret dans `.env.local` seulement, puis vrai `GET /health` affichant 200 et latence ; échec maintenu « non vérifié ». | Aucun formulaire, aucune écriture `.env.local`, aucun appel health, aucune latence ou état « non vérifié ». L'absence de `.env.local` n'est pas expliquée. | Bloquant pour la démo |
| LLM V1 — 2. Guider | Checklist proposée par le cerveau local et validée manuellement ; aucun auto-armement. | Aucun écran de checklist, aucune case de validation, aucun statut de préparation lisible. | Bloquant pour la démo |
| LLM V1 — 3. Armer | Pour Codex, Claude et distant : pastilles Pont Up → token OK → un PONG réel. Vert seulement si les trois preuves sont réelles ; cause claire sinon. | Aucun harnais, aucune sonde affichée, aucun POST PONG ni état token/pont. Le bandeau santé et l'éclair distant existants ne sont pas ces preuves. | Bloquant pour la démo |
| LLM V1 — 4. Essayer | Un tour PTT par harnais armé ; réponse réellement affichée et parlée, ou fallback parlé et textuel « je reste en local ». | Il n'existe qu'un PTT vers le WebSocket host-agent par défaut. Il ne choisit pas de harnais et ne propose aucun fallback local parlé. | Bloquant pour la démo |
| LLM V1 — langue et preuves | Les quatre étapes affichent leurs preuves, « FR only ». | Le wizard courant propose Français / English et les chaînes UI ont une traduction anglaise. Surtout, les preuves LLM exigées n'existent dans aucune langue. | Visible |
| Tests LLM V1 | Tests health 200/KO, refus sans PONG, fallback, copies FR, plus captures des quatre écrans. | `dev/tests/test_presence_onboarding_llm.py` est absent. Le seul fichier livré contient 23 tests PTT/visuels ; son test Tk force `session_lancee=True`, donc ne teste ni le micro, ni le serveur, ni les harnais. | Bloquant pour la fiabilité de la démo |
| Poste vierge — modèle/service absent | Muse promet un premier essai guidé ; LLM V1 interdit de laisser croire à une connexion sans preuve. | Après « Commencer », le fil importe `native.hostagent.talk`, tente les dépendances audio puis `ws://127.0.0.1:8001/hostagent`. Sans modèle/service, il affiche une erreur textuelle (« Dépendance audio absente », « sounddevice ou websockets absent », ou « Impossible de joindre … »). Le PTT affiche ensuite « Canal pas encore prêt ». Pas de chargement, diagnostic actionnable ou repli. | Bloquant pour la démo sur machine vierge |
| Poste vierge — permission micro refusée | Erreur micro immédiate, textuelle, non bloquante, avec une voie claire pour continuer sans voix (Muse) ; aucun micro nécessaire durant le wizard (Codex). | Le wizard reste effectivement sans micro et l'échec après sa sortie est attrapé en texte (« Périphérique audio indisponible. Vérifiez le micro. »). Mais aucun écran ne détecte/refuse explicitement la permission Windows, n'explique comment la corriger ni ne propose un parcours texte/essai utile une fois le canal absent. | Bloquant pour la démo sur machine vierge |
| Poste vierge — aucun `.env.local` | Déclarer doit conserver les secrets dans `.env.local`, sans commit, et prouver le distant avant de l'armer. | Aucun onboarding ne crée ou ne lit cette configuration. Pour le host-agent, `talk.lire_secret()` emploie à la place le secret de développement si `MOTHER_HOSTAGENT_SECRET` est absent : l'app ne plante pas pour cette seule absence, mais une poignée de main réelle peut être refusée et l'utilisateur ne sait pas quoi configurer. | Bloquant pour la démo LLM |
| Recette a11y réelle | Le parcours clavier est requis ; le design demande une passe NVDA/Narrator avant diffusion. | Des contrôles Tab, focus visible et texte sont codés, mais aucun test ne parcourt Tab/Entrée de bout en bout, ne vérifie le rappel après réduction, ni ne couvre Narrator/NVDA. Les zones de transcript sont exclues du parcours Tab (`takefocus=0`). | Souhaitable |

## Conformités importantes à ne pas refaire

- Sans `presence.json`, `charger_configuration()` retourne la configuration par
  défaut avec `onboarding_termine=False` : Bienvenue est donc montrée.
- Le fil `SessionVocale` n'est démarré qu'à `_afficher_application()` ; les
  quatre écrans peuvent être parcourus avant toute tentative micro/WebSocket.
- Le choix Espace / Ctrl+Espace est validé, persisté par fichier temporaire puis
  remplacement, et restauré ; un JSON invalide revient à Espace.
- Dans l'application, souris, raccourci configuré et Entrée sur le bouton PTT
  appellent bien la logique d'appui/relâchement ; le libellé limite honnêtement le
  raccourci à la fenêtre ayant le focus.
- Le masquage réel est `iconify()`, non `withdraw()`. Croix ferme ; Échap ferme
  hors lecture et coupe la voix pendant une lecture.
- La conversation conserve transcript, réponse et statut textuels. L'éclair
  distant est accompagné du texte « Appel distant » et d'une phrase explicite.

## Scénario jury : lancement vierge

Chemin observé sans `.env.local`, sans modèle/service téléchargé et avec micro
non autorisé :

```text
Bienvenue → Mains libres → PTT → Masquage → Commencer
                                      ↓
                         UI principale + démarrage SessionVocale
                                      ↓
     dépendance / micro / WebSocket indisponible → erreur texte
                                      ↓
                    PTT : « Canal pas encore prêt »
```

Ce chemin ne bloque pas techniquement le wizard, ce qui respecte le minimum
Codex. Il échoue cependant comme démonstration de l'assistante : aucune réponse,
aucune voix, aucun PONG ni fallback n'est possible. Le secret de développement
évite seulement une panne due à la variable manquante ; il ne remplace ni le
service ni une configuration vérifiée.

## Classement

### A FAIRE ABSOLUMENT AVANT LE 25

- Décider explicitement que LLM V1 est dans la soutenance et, si oui, réaliser
  ses quatre écrans avec leurs preuves réelles : Déclarer (health 200/latence),
  Guider, Armer (Up/token/PONG) et Essayer (réponse ou fallback local visible et
  parlé). Sans cela, ne pas présenter ce flux comme livré.
- Rendre le lancement vierge démontrable : diagnostic avant/après le wizard pour
  dépendances, modèle/service, secret et permission micro ; une action de
  correction ou un vrai mode texte/local dégradé est nécessaire. Ne pas laisser
  le jury sur « Canal pas encore prêt ».
- Ajouter les tests LLM V1 prescrits et un test d'intégration simulant exactement
  configuration absente + health KO + micro indisponible + fallback. Faire aussi
  une répétition interactive sur le poste destiné au jury.
- Si le PTT au maintien reste la promesse de démo, ne pas laisser « Mains libres »
  changer silencieusement ce contrat : soit le retirer du parcours de démo, soit
  l'expliquer comme un choix de mode avant l'essai et le tester.

### SOUHAITABLE

- Faire de « Commencer et masquer » l'issue normale ou masquer automatiquement,
  puis afficher le rappel discret PTT/rappel de fenêtre.
- Réconcilier la copy avec le flux réellement vendu : quatre réglages au lieu de
  deux/trois, ou alléger le wizard.
- Verrouiller le français pour les écrans LLM de soutenance et vérifier
  réellement Tab/Entrée, réduction/rappel et Narrator/NVDA.
- Si la promesse Muse est maintenue, ajouter le chargement calme et le bonjour
  sous-titré du modèle seulement une fois qu'un modèle réellement disponible peut
  le produire.

### ABANDONNER

Pour cette tranche et cette soutenance, conformément au design Codex :

- La vidéo optionnelle et son orchestration d'overlay.
- Le raccourci global Windows (`RegisterHotKey`) et la gestion des collisions.
- Une tray icon dédiée ; l'icône de la barre des tâches et `iconify()` suffisent.
- Le parcours Muse entièrement piloté à la voix tant que la machine vierge ne
  garantit pas qu'un modèle local et le micro sont prêts : il contredit la
  propriété utile du wizard PTT, terminable sans audio.
