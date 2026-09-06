"""
Handlers pour les jobs Camunda night_health_vault_note.
Python stdlib only (urllib, json, pathlib, time).
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple


def handle_health_check(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exécute le health-check de la topologie Camunda.
    DEGRADED n'est pas un échec de job (complete quand même).
    """
    topology_url = variables.get("topologyUrl", "http://127.0.0.1:8088/v2/topology")
    
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start_time = time.time()
    
    http_status = 0
    health_status = "DEGRADED"
    cluster_size = 0
    brokers_count = 0
    partitions_count = 0
    gateway_version = "unknown"
    
    try:
        req = urllib.request.Request(topology_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            http_status = resp.status
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)
            
            cluster_size = data.get("clusterSize", 0)
            partitions_count = data.get("partitionsCount", 0)
            gateway_version = str(data.get("gatewayVersion", "unknown"))
            brokers = data.get("brokers", [])
            brokers_count = len(brokers) if isinstance(brokers, list) else 0
            
            if http_status == 200 and brokers_count > 0:
                health_status = "UP"
            else:
                health_status = "DEGRADED"
    except Exception as e:
        # En cas d'erreur de connexion, on renseigne le status DEGRADED avec le code si dispo
        if isinstance(e, urllib.error.HTTPError):
            http_status = e.code
        else:
            http_status = 503
        health_status = "DEGRADED"
        gateway_version = f"error: {str(e)}"
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "healthStatus": health_status,
        "httpStatus": http_status,
        "clusterSize": cluster_size,
        "brokersCount": brokers_count,
        "partitionsCount": partitions_count,
        "gatewayVersion": gateway_version,
        "checkedAt": checked_at,
        "latencyMs": latency_ms,
    }


def handle_vault_note(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Écrit la note de santé dans le coffre Obsidian et la relit avant complétion.
    """
    night_date = variables.get("nightDate", "2026-08-31")
    vault_dir_raw = variables.get("vaultDir", r"C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights")
    
    vault_dir = Path(vault_dir_raw)
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    note_file = vault_dir / f"{night_date}-HEALTH.md"
    
    # Récupération des variables de santé
    health_status = variables.get("healthStatus", "UNKNOWN")
    http_status = variables.get("httpStatus", "N/A")
    brokers_count = variables.get("brokersCount", "N/A")
    cluster_size = variables.get("clusterSize", "N/A")
    partitions_count = variables.get("partitionsCount", "N/A")
    gateway_version = variables.get("gatewayVersion", "N/A")
    latency_ms = variables.get("latencyMs", "N/A")
    checked_at = variables.get("checkedAt", "N/A")
    
    content = f"""---
date: {night_date}
tags: [project/mother, camunda, health, nuit]
process: night_health_vault_note
---

# Health — nuit du {night_date}

| Champ | Valeur |
|---|---|
| Statut | {health_status} |
| HTTP | {http_status} |
| Brokers | {brokers_count} |
| Cluster size | {cluster_size} |
| Partitions | {partitions_count} |
| Gateway | {gateway_version} |
| Latence | {latency_ms} ms |
| Vérifié à | {checked_at} |

Écrit par le process Camunda `night_health_vault_note` (task `write_vault_note`).
"""

    # Écriture UTF-8 avec newline \n
    with open(note_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    
    # Relecture obligatoire
    if not note_file.exists():
        raise RuntimeError(f"Le fichier {note_file} n'a pas pu être créé.")
    
    with open(note_file, "r", encoding="utf-8") as f:
        read_content = f.read()
    
    note_bytes = len(read_content.encode("utf-8"))
    note_written = (read_content == content) and (note_bytes > 0)
    
    if not note_written:
        raise RuntimeError("La vérification par relecture de la note a échoué.")
    
    return {
        "notePath": str(note_file),
        "noteBytes": note_bytes,
        "noteWritten": True,
    }
