---
date: 2026-09-13
type: diagnostic-codex
incident: voix-regression-17h05
role: cerveau-read-only
---
# Codex — diagnostic régression voix

## Verdict court

Le revert runtime est confirmé : un seul host-agent, PID `7100`, utilise Piper
`fr_FR-siwis-medium` avec `aurora` à 22 050 Hz. Il n'est pas encore figé dans
les défauts du dépôt.

La régression perçue suit directement le switch `siwis+aurora -> upmc+mother`.
Le profil `mother` est le premier suspect qualitatif : réverbe 22 %, doublage
17 ms à 16 %, débit ralenti de 16 %. Il peut transformer les coutures de Piper
en texture brouillée ou hachée. Le revert est donc la bonne mesure P0.

Une seconde cause probable se situe dans la restitution Windows. Le serveur
normalise tout à 16 kHz, mais la sortie par défaut est Sound Blaster Z via MME,
native 44,1 kHz. Le dernier rééchantillonnage est implicite. Le client lit un
message WebSocket puis appelle `OutputStream.write()` de façon bloquante, sans
mesurer underflow ni espacement réel. La recette concatène les paquets et peut
masquer les trous. Il faut instrumenter ce point avant de réécrire le transport.

`tom-mother.wav` à 44,1 kHz est hors production. Les deux voix actives possibles,
siwis et upmc, sortent à 22,05 kHz ; le fichier Tom ne peut donc pas expliquer
le changement du jour. Un seul client `pythonw native/presence/app.py` tourne :
pas de double speak observé.

## Qualité des réponses

MiniCPM5-2B est réellement chargé, mais il classe les tours et répond seulement
aux réflexes. L'exemple mauvais du facteur temps réel a été routé `escalate` :
la réponse erronée sur le nombre de Courant vient du canal distant
MiniMaxAI/MiniMax-M3. Le prompt système impose surtout persona et texte oral ;
il ne demande ni vérification factuelle ni clarification. La génération utilise
la température par défaut `0.7`.

Les fillers ne rendent pas la réponse plus analysée. Ils ne font que couvrir la
latence et peuvent accentuer l'impression de parole morcelée. Le runtime affiche
en outre `OUTILS: aucun` : sans jeton de pont, Codex n'est pas disponible depuis
la boucle vocale.

Recommandation : température `0.2`, consigne courte de rigueur dans le prompt,
politique d'escalade conservée, une seule amorce, puis gate factuel fixe avant
tout choix de modèle. Ne pas attribuer la mauvaise réponse à MiniCPM sans preuve.

## Niveau de confiance

- élevé : revert actif, configuration non persistante, modèle local réellement
  chargé, réponse fautive issue de l'escalade, absence de double processus ;
- moyen-élevé : `mother` a dégradé la perception lors du switch ;
- moyen : trous dus à MME/lecture bloquante ou starvation entre paquets ; les
  logs actuels ne contiennent pas les horodatages nécessaires pour trancher ;
- faible/écarté : Tom 44,1 kHz, double speak, mismatch siwis contre upmc.

Les patches et commandes exactes destinés à Cursor sont dans
`nights/2026-09-13-ORDRE-CURSOR-VOIX-REGRESSION.md`.
