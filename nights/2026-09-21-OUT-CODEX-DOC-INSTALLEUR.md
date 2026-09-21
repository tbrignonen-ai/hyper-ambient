# Compte rendu — documentation et installeur

## Écrit

- `README.md` a été repris comme page d’arrivée : produit, limite assumée pour le
  développement intensif, architecture Docker / agent hôte / Presence Tkinter,
  prérequis matériels (budget GPU total de 8 à 10 Go), installation Windows et
  prochaines étapes.
- `README.en.md` porte le même périmètre dès le jour 1, sans présenter l’anglais
  comme une documentation secondaire.
- `packaging/windows/README.md` donne des commandes PowerShell appelables depuis
  n’importe quel répertoire, avec un chemin entre guillemets et un diagnostic
  obligatoire avant l’installation. Il explique les actions réelles du script,
  son caractère reprenable et l’absence de dépendances applicatives sur le Python
  hôte.
- Le guide Windows explique Docker Desktop exactement : `winget` peut installer le
  paquet sans interaction dans la limite de son contrat, mais la première fenêtre
  Docker exige l’acceptation humaine de sa licence. L’installeur lance Docker,
  attend au plus 180 secondes le moteur et demande de relancer après le consentement.
- `DONNEES.md` et `DONNEES.en.md` indiquent désormais que tous les tours difficiles
  et ceux qui nomment Codex, Claude Code ou Cursor vont au modèle distant. Les
  ponts locaux sont explicitement séparés des sorties réseau éventuelles de la CLI
  connectée par l’utilisateur.
- Les deux fichiers de données recensent les transcriptions Markdown locales :
  `%LOCALAPPDATA%\hyper-ambient\conversations\YYYY-MM-DD_HH-mm.md`, écrites
  progressivement, lisibles dans un éditeur et sans envoi réseau.

## Vérifié

- Lecture statique complète de `packaging/windows/installer.ps1` : il se repère avec
  `$PSScriptRoot`, diagnostique avant action, installe Python/WSL2/Docker quand ils
  manquent, démarre Docker, construit puis démarre `mother-core-dev` et délègue les
  raccourcis. Le script crée seulement une configuration locale vide ou depuis son
  exemple ; il n’installe pas les dépendances de l’application sur le Python hôte.
- Le compte rendu de vérification précédent confirme une exécution avec
  `-Diagnostic`, sortie 0 et `Verdict : pret`. Cette tâche n’a pas exécuté
  l’installeur sans `-Diagnostic`.
- Le chemin, le format Markdown et l’écriture incrémentale des transcriptions ont
  été vérifiés contre le brief de la tâche dédiée à l’agent hôte ; son code reste
  hors périmètre documentaire.
- Les écarts publiés viennent de
  `2026-09-20-IMPLEMENTATIONS-FUTURES.md` et des rapports de nuit : macOS non
  exécuté sur matériel réel, espagnol repoussé, onboarding assisté remplacé par
  menus, vidéo/tray/raccourci global, accessibilité en parcours réel, continuité
  de mémoire et de mandats, reprise serveur et sonde de santé.

## Étapes manuelles signalées, automatisables

Ces points ne sont pas corrigés ici ; ils relèvent de l’agent qui tient le code.

1. **Obtenir le dépôt avant le premier lancement.** Le script vit dans le clone et
   ne peut donc pas cloner son propre point d’entrée. Un petit bootstrap publié
   (archive ou clone, avec vérification d’intégrité) peut ensuite appeler ce script.
2. **Télécharger les modèles et exécuter le contrôle de santé.** Après le conteneur,
   le script se contente d’annoncer `make models`, `make models-brain`, `nvidia-smi`
   et le smoke test. Un mode explicite, avec estimation de taille et consentement,
   peut les enchaîner dans le conteneur puis rapporter le résultat.
3. **Démarrer le chemin vocal après l’amorçage.** Le host-agent, les serveurs de
   modèles et Presence ne sont pas lancés par l’installeur. Un lanceur contrôlé peut
   les démarrer et vérifier les endpoints locaux.
4. **Réglages WSL/Docker vérifiables.** La mémoire WSL et le moteur WSL2/GPU de
   Docker sont seulement signalés. Un mode avec accord explicite peut écrire une
   configuration proposée, relancer Docker et vérifier la disponibilité GPU.
5. **Pilote NVIDIA.** Le script détecte un pilote trop ancien, mais ne le met pas à
   jour. Une mise à jour peut être préparée et lancée avec consentement explicite,
   après sélection du pilote correspondant réellement au GPU.

Le BIOS/UEFI, le redémarrage Windows, l’acceptation de la licence Docker Desktop et
les identifiants de services restent des interventions humaines : ils ne doivent pas
être contournés par automatisation.
