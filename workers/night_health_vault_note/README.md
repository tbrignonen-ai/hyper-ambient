# Worker Camunda stdlib — `night_health_vault_note`

Worker Python 3 standard library uniquement (aucun `pip`, aucun SDK Zeebe externe) pour le process Camunda `night_health_vault_note`.

## Rôles & Job Types

Ce worker écoute en boucle via Camunda REST API v2 (`POST /v2/jobs/activation`) :
1. **`health-check`** :
   - Sonde les ponts Codex `:8765`, Claude `:8766`, l'accueil vocal `:8001` et le modèle local `:8090`.
   - Une réponse HTTP (même 4xx/5xx) compte comme vivant ; refus de connexion / timeout = panne.
   - Renseigne encore `topologyUrl` (défaut : `http://127.0.0.1:8088/v2/topology`) si Camunda tourne.
   - `DEGRADED` si un endpoint nommé ne répond pas, avec `alertMessage` / `recoveryMessage` en français simple.
   - `DEGRADED` n'est pas un échec de job (le job est complété pour permettre la génération de la note).

2. **`vault-note`** :
   - Lit les variables produites par `health-check` et les variables de contexte (`nightDate`, `vaultDir`).
   - Écrit la note Markdown dans `{vaultDir}/{nightDate}-HEALTH.md` (composants nommés + phrase d'alerte).
   - Relit et valide le fichier avant d'envoyer la complétion.
   - Produit les variables : `notePath`, `noteBytes`, `noteWritten`.

## Utilisation

Lancement Camunda :
```bash
python worker.py --camunda-url http://127.0.0.1:8088
```

Mode dégradé (Camunda absent, **sans** `docker compose`) :
```bash
python worker.py --once --night-date 2026-09-19 --snapshot %LOCALAPPDATA%\hyper-ambient\sante.json
```

Le fichier témoin `.worker-up` signale aux orchestrateurs (ou scripts externes) que le worker est en attente de jobs.
