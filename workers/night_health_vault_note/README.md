# Worker Camunda stdlib — `night_health_vault_note`

Worker Python 3 standard library uniquement (aucun `pip`, aucun SDK Zeebe externe) pour le process Camunda `night_health_vault_note`.

## Rôles & Job Types

Ce worker écoute en boucle via Camunda REST API v2 (`POST /v2/jobs/activation`) :
1. **`health-check`** :
   - Récupère `topologyUrl` (défaut : `http://127.0.0.1:8088/v2/topology`).
   - Évalue la santé du cluster (`UP` si HTTP 200 + brokers > 0, sinon `DEGRADED`).
   - Produit les variables : `healthStatus`, `httpStatus`, `clusterSize`, `brokersCount`, `partitionsCount`, `gatewayVersion`, `checkedAt`, `latencyMs`.
   - `DEGRADED` n'est pas un échec de job (le job est complété pour permettre la génération de la note).

2. **`vault-note`** :
   - Lit les variables produites par `health-check` et les variables de contexte (`nightDate`, `vaultDir`).
   - Écrit la note Markdown dans `{vaultDir}/{nightDate}-HEALTH.md`.
   - Relit et valide le fichier avant d'envoyer la complétion.
   - Produit les variables : `notePath`, `noteBytes`, `noteWritten`.

## Utilisation

Lancement :
```bash
python worker.py --camunda-url http://127.0.0.1:8088
```

Le fichier témoin `.worker-up` signale aux orchestrateurs (ou scripts externes) que le worker est en attente de jobs.
