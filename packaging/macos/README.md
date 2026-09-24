# MOTHER Mac 16 Go VOIX MAX — paquet DEV

Profil explicite `mac-16g-voix-max` pour macOS arm64. Le serveur vocal est
`dev/scripts/serve_hostagent.py` natif ; `src/core/app.py` reste un placeholder.
Le chemin conteneur CUDA et les lanceurs Windows ne sont pas utilisés.

## Préparer la machine

1. Installer Python **3.12 arm64** avec Tk utilisable depuis Finder/Terminal.
   Créer un venv Mac séparé, puis installer `requirements-macos.txt`. La
   résolution PyPI arm64 a été vérifiée sur BillieBoy, l'installation Mac non.
2. Copier `mac-16g.env.example` dans un fichier personnel et définir
   `MOTHER_TTS_REFERENCE_WAV` vers un WAV de voix dont l'usage est autorisé.
   `MOTHER_MODELS_DIR` peut pointer vers un disque ayant au moins 30 Go libres.
3. Inspecter `models.lock.json`, puis télécharger **explicitement** chaque
   famille avec `python dev/scripts/models_macos.py download --family FAMILLE`.
   Ordre : `jev`, `tts_s3`, `tts`, `stt`, `text`. Les RU se téléchargent seulement
   si la recette les demande. Le downloader reprend dans `.partial`, vérifie
   SHA-256 LFS ou Git blob SHA-1 et publie le snapshot après vérification.
   Chatterbox a besoin de `tts_s3` en plus de ses propres fichiers. Le cache
   HF de cet auxiliaire est alimenté localement, hors ligne, sans doublon de
   poids grâce à des liens physiques. Aucun lancement ne télécharge de modèle.
4. `python dev/scripts/preflight_macos.py --config /chemin/mac.env --dry-run`
   affiche les actions et statuts sans démarrer de service ni ouvrir le micro.
   Le vrai lancement refuse Mac non arm64, modèles manquants, référence absente
   et port déjà occupé.
5. `chmod +x packaging/macos/lancer.command`, puis ouvrir ce `.command` dans
   Terminal/Finder avec `HYPERAMBIENT_PYTHON` pointant sur le venv arm64 et
   `MOTHER_MAC_CONFIG` pointant sur le fichier personnel. Le lanceur est suivi
   avec le mode Git exécutable 100755.

Le superviseur ouvre le service texte, les ponts configurés, le host-agent,
puis Presence. Il n'arrête que ses enfants. Les journaux sont dans
`~/Library/Logs/MOTHER` (ou `MOTHER_LOG_DIR`), sans valeur de jeton. Les ponts
répondent à un `/health` authentifié ; un port occupé par un autre service
bloque le lancement. Une session Claude/Codex ouverte dans Terminal appartient
à l'utilisateur et reste ouverte après la fermeture de Presence.

## Limites à mesurer sur un vrai Mac

- Le JeV DeBERTa, modèle anglais avec fenêtre 512 tokens, répond aux 19
  questions françaises en plusieurs passes. Le budget de 600 ms et les seuils
  d'adressage doivent être vérifiés sur le corpus FR/EN ; un timeout rend
  `None` et n'ouvre aucun droit. Aucun LLM ne remplace JeV.
- STT et TTS se partagent un résident MLX et un worker borné. Le texte MLX-LM
  et le JeV MPS restent dans d'autres moteurs. Les pics mémoire, la recharge,
  l'annulation de calcul Metal déjà lancé restent à mesurer. Le lanceur utilise
  `native.macos.text_server`, adaptateur strict de MLX-LM 0.31.3 : après le
  template et la tokenisation réels, entrée + budget de sortie doivent tenir
  dans 2 048 tokens. La sortie est plafonnée à 256 tokens. Un dépassement est
  rejeté avant cache/prefill, sans tronquer les consignes ni les outils ; le
  serveur amont renvoie une erreur HTTP 404 JSON, y compris en mode streaming.
  La concurrence serveur reste à 1. Ce budget par requête ne borne pas la RAM
  globale. Les contrats sont testés sans Metal ; l'intégration réelle reste
  à éprouver sur Mac. Lancer directement `mlx_lm.server` contourne cette garde.
- Chatterbox v3 est segmenté par phrase : pas de streaming audio intra-phrase.
  `lang_code=fr`/`en`, voix de référence et paramètres fixes sont utilisés.
  Le timbre Sofia n'est pas présumé. Vérifier aussi les poids auxiliaires S3.
- Le micro tente 16 kHz puis le taux CoreAudio du périphérique avec SoXR
  continu ; la sortie suit la même logique. Un callback muet ne prouve ni
  permission TCC ni qualité de capture. Tester les périphériques, retraits et
  retours sur place. La permission Microphone est liée à l'interpréteur qui
  lance Presence, puis au bundle signé si un `.app` est créé. Le helper
  Terminal de reprise n'utilise pas Automation ; Accessibilité n'est pas
  nécessaire pour la capture.
- Le routeur Mac classe via `/v1/chat/completions` et accepte seulement
  `REFLEXE` exact ; toute autre sortie escalade. Tester les flux d'outils et
  l'historique avec la conversion LFM réelle avant de considérer ce chemin
  prêt. La licence du texte est `other` (`lfm1.0`) et celle du RU Ministral
  aussi `other` : lire leurs conditions avant toute distribution. Kyutai RU
  est CC-BY-4.0 avec attribution à préparer. Aucun `.app` signé/notarisé
  n'est livré ici.
- La bascule rapide de cerveau passe par les options WebSocket. Le bouton
  « Appliquer » du panneau Réglages persiste le choix mais ne relance pas le
  host-agent natif sous Mac ; la garde retourne un échec explicite et ne
  touche pas au conteneur Windows. Relancer le superviseur pour prendre en
  compte ce réglage, ou utiliser la bascule rapide pendant une session.

## Révisions

Les 8 snapshots, leurs API HF, fichiers, tailles et digests sont dans
`models.lock.json` ; `tts_s3` est l'auxiliaire du TTS, les 3 familles `_ru`
sont les réserves. Le code de lecture JeV vendored est comparé aux Git blob
SHA-1 de la révision `19bf9a6` lors du préflight. Ces preuves de provenance
ne valent pas validation d'inférence ni autorisation de distribution.
