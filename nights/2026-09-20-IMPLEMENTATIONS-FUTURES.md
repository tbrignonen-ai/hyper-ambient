# Implémentations futures

Ce document reprend les écarts relevés le 20 septembre. Ces éléments ne sont
pas livrés ce soir.

## macOS

Le terminal macOS est écrit autour de `platform_audio` et `platform_ui`. Leurs
15 tests existent, ainsi que le rapport de Fable :
`2026-09-20-OUT-FABLE-MACOS.md`. Ce travail n'a jamais été exécuté sur un vrai
Mac. Il ne faut pas le présenter comme validé.

Des collègues le testeront sur un Mac réel cette semaine : micro, son, fenêtre
et connexion au cœur. Le cœur reste sur GPU NVIDIA par choix. Le Mac est un
terminal, pas une seconde pile d'inférence.

## Installation et réglages

L'onboarding conversationnel, assisté par le modèle local, est spécifié. Il
est remplacé ce soir par un écran de réglages classique.

Il reste à faire : déclarer un service distant et le vérifier réellement,
guider les prérequis, armer chaque pont avec ses preuves, puis proposer un
premier essai et un repli local clair. L'état du parcours doit pouvoir être
repris. Les tests et captures de ce parcours manquent aussi.

Le modèle local doit aussi devenir un assistant de diagnostic dans les
réglages. Une machine sans modèle, micro, dépendance ou service doit recevoir
une cause et une action utile, pas seulement un canal indisponible.

## Langues et interface

Le français et l'anglais sont livrés. L'espagnol reste à terminer dans
l'interface et le parcours de réglages.

La vidéo optionnelle, le masquage automatique et son rappel, le raccourci
global Windows et une icône de zone de notification ne sont pas livrés. Le
wizard devra aussi être réconcilié avec le parcours plus court qu'il annonçait.
Ces choix seront réévalués après le parcours de base. L'accessibilité doit
encore être vérifiée dans un vrai parcours clavier et avec Narrator ou NVDA.

## Continuité et outils

La recherche doit pouvoir répondre clairement à une question sur sa propre
disponibilité, au lieu de laisser ce choix au modèle. La mémoire vocale doit
garder un fil plus long et expirer un résultat d'outil après son tour de suivi.

Les notifications de mandat doivent former un tour complet. Un redémarrage du
serveur ne doit pas perdre silencieusement un tour en cours. Le mode mains
libres doit correspondre à son texte d'interface. Enfin, les journaux doivent
partager un identifiant de tour et la sonde de santé doit viser le bon endpoint.
