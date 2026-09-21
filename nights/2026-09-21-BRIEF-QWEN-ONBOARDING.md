# Nuit B — l'onboarding simple doit marcher, et ses sondes doivent dire vrai

Bonjour, je suis Opus et je travaille pour Human IA. Le fondateur dort. Tu es **seul
propriétaire** cette nuit de `src/onboarding/`, `native/presence/reglages_ui.py` et de
leurs tests. D'autres agents travaillent en parallèle ailleurs : ne sors pas de ce
périmètre.

## La consigne du fondateur

« Pour le onboarding, essayez de le tester. On fait la version simple mais il faut
qu'elle marche. »

Pas d'onboarding piloté par l'IA : des **menus de configuration dans l'application**,
qui fonctionnent réellement. Ce qui doit être configurable : le modèle externe, la
connexion avec les harnais (Codex, Claude Code), la connexion avec JeV, la langue, la
voix et l'accent.

## Défaut connu à corriger en priorité — les sondes sont creuses

Une revue précédente a relevé que `sonder_codex` répond `ok=True` en 13 ms. Ce délai est
impossible pour un vrai aller-retour vers un harnais : la sonde envoie une **question
vide**, et ne prouve donc que l'existence du pont et la validité du jeton — pas que le
harnais répond. De même, `outil_cli_pret` vérifie la présence d'un exécutable et non
l'existence d'un abonnement actif.

Un voyant vert qui ne prouve rien est pire que pas de voyant : l'utilisateur configure,
voit vert, et découvre la panne en démonstration. Corrige donc les sondes pour qu'elles
posent une **vraie question minimale** dont la réponse est vérifiable, avec un délai
d'attente borné, et que le libellé affiché distingue honnêtement trois états : joignable
et répond / joignable mais ne répond pas / injoignable. Dis clairement dans ton rapport
ce que chaque voyant prouve désormais.

## Tester réellement, pas seulement unitairement

Le fondateur a déjà refusé une fois de tester du travail inachevé. **Teste l'onboarding
toi-même de bout en bout avant de le déclarer prêt** :

- Ouvre la fenêtre de réglages et vérifie qu'on peut saisir une valeur, la voir, la
  sauvegarder et la relire après redémarrage. Les champs avaient été invisibles à cause
  d'un `relief=tk.FLAT` sur fond sombre ; vérifie qu'ils sont lisibles.
- Vérifie que « Vérifier » et « Tout vérifier » appellent bien les sondes corrigées et
  affichent un état honnête.
- Vérifie le cas d'une **installation neuve** : aucun réglage posé, aucune clé. Rien ne
  doit planter. Un `HA_LANG` absent avait déjà provoqué un `ValueError: langue invalide`
  au démarrage ; cherche les autres valeurs par défaut manquantes du même genre.
- Vérifie que rien de ce que tu affiches ne révèle la valeur d'une clé API : un jeton se
  montre masqué, jamais en clair, ni dans l'interface, ni dans un journal, ni dans ton
  rapport.

## Tests

TDD, rouge d'abord. Colle la sortie de :
`python -m pytest dev/tests -q -k "onboarding or reglages or sondes"`
puis celle de la suite complète `python -m pytest dev/tests -q`.

## Contraintes

- Périmètre : `src/onboarding/`, `native/presence/reglages_ui.py` et leurs tests.
  **Ne touche pas** à `dev/scripts/serve_hostagent.py`, `src/brain/`,
  `dev/scripts/carte_figee.env`, `.env.local`, `README.md`, `packaging/` — d'autres
  agents les tiennent cette nuit.
- Aucune commande git : ni branche, ni commit, ni push.
- Rien ne s'installe sur le Python de l'hôte : tout passe par le conteneur
  `mother-core-dev`.
- Compte rendu dans `nights/2026-09-21-OUT-QWEN-ONBOARDING.md`, avec les sorties de
  commande et la liste de ce que tu as réellement vu fonctionner.
