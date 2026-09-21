"""
Handlers pour les jobs Camunda night_health_vault_note.
Python stdlib only (urllib, json, pathlib, time).
Sonde les ponts et services locaux ; Camunda est optionnel (mode dégradé).
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple


PHRASES_ALERTE = {
    "pont_codex": "Le pont vers Codex ne répond plus, je continue en local.",
    "pont_claude": "Le pont vers Claude ne répond plus, je continue en local.",
    "host_agent": "L'accueil vocal ne répond plus.",
    "modele_local": "Le modèle local ne répond plus.",
    "camunda": "Le suivi automatique n'est pas disponible, je surveille en direct.",
}

PHRASES_REPRISE = {
    "pont_codex": "Pont Codex rétabli.",
    "pont_claude": "Pont Claude rétabli.",
    "host_agent": "Accueil vocal rétabli.",
    "modele_local": "Modèle local rétabli.",
    "camunda": "Suivi automatique rétabli.",
}

DEFAULT_ENDPOINTS = [
    {"id": "pont_codex", "nom": "pont Codex", "url": "http://127.0.0.1:8765/ask"},
    {"id": "pont_claude", "nom": "pont Claude", "url": "http://127.0.0.1:8766/ask"},
    {"id": "host_agent", "nom": "accueil vocal", "url": "http://127.0.0.1:8001/"},
    {"id": "modele_local", "nom": "modèle local", "url": "http://127.0.0.1:8090/health"},
]


def sonder_url(url: str, timeout: float = 1.5) -> Tuple[bool, int]:
    """Toute réponse HTTP (même 4xx/5xx) = process vivant. Refus / timeout = panne."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, int(resp.status)
    except urllib.error.HTTPError as exc:
        return True, int(exc.code)
    except Exception:
        return False, 0


def phrase_alerte(ident: str, nom: str) -> str:
    return PHRASES_ALERTE.get(ident, f"{nom} ne répond plus.")


def phrase_reprise(ident: str, nom: str) -> str:
    return PHRASES_REPRISE.get(ident, f"{nom} rétabli.")


def _normaliser_endpoints(variables: Dict[str, Any]) -> List[Dict[str, str]]:
    if "endpoints" in variables:
        bruts = variables.get("endpoints") or []
    else:
        bruts = list(DEFAULT_ENDPOINTS)
    if isinstance(bruts, str):
        try:
            bruts = json.loads(bruts)
        except json.JSONDecodeError:
            bruts = []
    sorties: List[Dict[str, str]] = []
    for item in bruts:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()
        url = str(item.get("url") or "").strip()
        if not ident or not url:
            continue
        sorties.append(
            {
                "id": ident,
                "nom": str(item.get("nom") or ident),
                "url": url,
            }
        )
    return sorties


def _sonder_topologie(topology_url: str) -> Dict[str, Any]:
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
    except Exception as exc:
        if isinstance(exc, urllib.error.HTTPError):
            http_status = exc.code
        else:
            http_status = 503
        health_status = "DEGRADED"
        gateway_version = f"error: {str(exc)}"

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
        "ok": health_status == "UP",
    }


def handle_health_check(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sonde les endpoints nommés. DEGRADED n'est pas un échec de job.
    Camunda (topologyUrl) reste renseigné s'il est joignable ; s'il ne l'est pas,
    le mode dégradé continue à sonder les ponts en stdlib.
    """
    start_time = time.time()
    topology_url = variables.get("topologyUrl", "http://127.0.0.1:8088/v2/topology")
    topo = _sonder_topologie(topology_url)

    composants: List[Dict[str, Any]] = [
        {
            "id": "camunda",
            "nom": "suivi automatique",
            "ok": bool(topo["ok"]),
            "httpStatus": topo["httpStatus"],
        }
    ]
    for endpoint in _normaliser_endpoints(variables):
        ok, statut = sonder_url(endpoint["url"])
        composants.append(
            {
                "id": endpoint["id"],
                "nom": endpoint["nom"],
                "ok": ok,
                "httpStatus": statut,
            }
        )

    hors_camunda = [c for c in composants if c["id"] != "camunda"]
    a_classer = hors_camunda if hors_camunda else composants
    en_panne = [c for c in a_classer if not c["ok"]]
    health_status = "DEGRADED" if en_panne else "UP"
    premier = en_panne[0] if en_panne else None

    alert_message = ""
    recovery_message = ""
    if premier is not None:
        alert_message = phrase_alerte(premier["id"], premier["nom"])
        recovery_message = phrase_reprise(premier["id"], premier["nom"])

    latency_ms = int((time.time() - start_time) * 1000)
    http_status = premier["httpStatus"] if premier is not None else topo["httpStatus"]

    resultat = {
        "healthStatus": health_status,
        "httpStatus": http_status,
        "clusterSize": topo["clusterSize"],
        "brokersCount": topo["brokersCount"],
        "partitionsCount": topo["partitionsCount"],
        "gatewayVersion": topo["gatewayVersion"],
        "checkedAt": topo["checkedAt"],
        "latencyMs": latency_ms,
        "alertMessage": alert_message,
        "recoveryMessage": recovery_message,
        "degradedComponents": ",".join(c["id"] for c in en_panne),
        "componentsJson": json.dumps(composants, ensure_ascii=False),
    }

    snapshot_path = variables.get("snapshotPath")
    if snapshot_path:
        cible = Path(snapshot_path)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(
            json.dumps(resultat, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return resultat


def dossier_notes_par_defaut() -> Path:
    """Ou deposer les notes quand l'appelant n'impose rien.

    Un chemin en dur vers le coffre d'un poste precis ne vaut que sur ce poste,
    et il y expose le nom de son proprietaire. La variable d'environnement
    ``HA_VAULT_DIR`` prend le pas ; sinon on retombe sous le dossier personnel,
    qui existe sur les trois systemes.
    """
    impose = os.environ.get("HA_VAULT_DIR", "").strip()
    if impose:
        return Path(impose)
    return Path.home() / "hyper-ambient" / "nights"


def handle_vault_note(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Écrit la note de santé dans le coffre Obsidian et la relit avant complétion.
    """
    night_date = variables.get("nightDate", "2026-08-31")
    vault_dir_raw = variables.get(
        "vaultDir", str(dossier_notes_par_defaut())
    )

    vault_dir = Path(vault_dir_raw)
    vault_dir.mkdir(parents=True, exist_ok=True)

    note_file = vault_dir / f"{night_date}-HEALTH.md"

    health_status = variables.get("healthStatus", "UNKNOWN")
    http_status = variables.get("httpStatus", "N/A")
    brokers_count = variables.get("brokersCount", "N/A")
    cluster_size = variables.get("clusterSize", "N/A")
    partitions_count = variables.get("partitionsCount", "N/A")
    gateway_version = variables.get("gatewayVersion", "N/A")
    latency_ms = variables.get("latencyMs", "N/A")
    checked_at = variables.get("checkedAt", "N/A")
    alert_message = variables.get("alertMessage") or ""
    degraded = variables.get("degradedComponents") or ""

    composants: List[Dict[str, Any]] = []
    brut_composants = variables.get("componentsJson") or "[]"
    if isinstance(brut_composants, list):
        composants = [c for c in brut_composants if isinstance(c, dict)]
    else:
        try:
            lu = json.loads(str(brut_composants))
            if isinstance(lu, list):
                composants = [c for c in lu if isinstance(c, dict)]
        except json.JSONDecodeError:
            composants = []

    lignes_composants = ["| Composant | État | HTTP |", "|---|---|---|"]
    if composants:
        for item in composants:
            etat = "UP" if item.get("ok") else "DOWN"
            lignes_composants.append(
                f"| {item.get('nom') or item.get('id')} | {etat} | {item.get('httpStatus', '')} |"
            )
    elif degraded:
        for ident in str(degraded).split(","):
            if ident.strip():
                lignes_composants.append(f"| {ident.strip()} | DOWN | |")
    table_composants = "\n".join(lignes_composants)

    bloc_alerte = ""
    if alert_message:
        bloc_alerte = f"\n**Alerte** : {alert_message}\n"

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
| Composants en panne | {degraded or "aucun"} |
{bloc_alerte}
{table_composants}

Écrit par le process Camunda `night_health_vault_note` (task `write_vault_note`).
"""

    with open(note_file, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)

    if not note_file.exists():
        raise RuntimeError(f"Le fichier {note_file} n'a pas pu être créé.")

    with open(note_file, "r", encoding="utf-8") as handle:
        read_content = handle.read()

    note_bytes = len(read_content.encode("utf-8"))
    note_written = (read_content == content) and (note_bytes > 0)

    if not note_written:
        raise RuntimeError("La vérification par relecture de la note a échoué.")

    return {
        "notePath": str(note_file),
        "noteBytes": note_bytes,
        "noteWritten": True,
    }
