"""
Worker Camunda stdlib-only pour night_health_vault_note.
Active les jobs health-check et vault-note en boucle via REST API v2.
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from handlers import (
    dossier_notes_par_defaut,
    handle_health_check,
    handle_vault_note,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

JOB_TYPES = ["health-check", "vault-note"]
DEFAULT_CAMUNDA_URL = "http://127.0.0.1:8088"
WORKER_NAME = "night-31-worker"


def activate_jobs(camunda_url: str, job_type: str, timeout: int = 30000, request_timeout: int = 5000) -> List[Dict[str, Any]]:
    """Active des jobs pour un type donné via POST /v2/jobs/activation."""
    url = f"{camunda_url.rstrip('/')}/v2/jobs/activation"
    payload = {
        "type": job_type,
        "worker": WORKER_NAME,
        "timeout": timeout,
        "maxJobsToActivate": 1,
        "requestTimeout": request_timeout,
        "fetchVariable": [
            "nightDate",
            "vaultDir",
            "topologyUrl",
            "healthStatus",
            "httpStatus",
            "clusterSize",
            "brokersCount",
            "partitionsCount",
            "gatewayVersion",
            "checkedAt",
            "latencyMs",
            "alertMessage",
            "recoveryMessage",
            "degradedComponents",
            "componentsJson",
            "snapshotPath",
            "endpoints",
        ]
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    
    try:
        # Long polling timeout + marge
        socket_timeout = (request_timeout / 1000.0) + 5.0
        with urllib.request.urlopen(req, timeout=socket_timeout) as resp:
            body = resp.read().decode("utf-8")
            if not body.strip():
                return []
            res_json = json.loads(body)
            if isinstance(res_json, list):
                return res_json
            if isinstance(res_json, dict):
                return res_json.get("jobs", [])
            return []
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logging.error(f"Erreur HTTP activation ({job_type}): {e.code} - {err_msg}")
        return []
    except Exception as e:
        # Timeout ou erreur réseau temporaire
        return []


def complete_job(camunda_url: str, job_key: str, variables: Dict[str, Any]) -> bool:
    """Complète un job via POST /v2/jobs/{jobKey}/completion."""
    url = f"{camunda_url.rstrip('/')}/v2/jobs/{job_key}/completion"
    payload = {"variables": variables}
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            logging.info(f"Job {job_key} complété avec succès (HTTP {resp.status}).")
            return True
    except Exception as e:
        logging.error(f"Erreur completion job {job_key}: {e}")
        return False


def fail_job(camunda_url: str, job_key: str, retries: int, error_message: str) -> bool:
    """Signale un échec de job via POST /v2/jobs/{jobKey}/failure."""
    url = f"{camunda_url.rstrip('/')}/v2/jobs/{job_key}/failure"
    payload = {
        "retries": max(0, retries - 1),
        "errorMessage": error_message[:500],
    }
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            logging.info(f"Job {job_key} marqué en échec (HTTP {resp.status}).")
            return True
    except Exception as e:
        logging.error(f"Erreur failure job {job_key}: {e}")
        return False


def process_job(camunda_url: str, job: Dict[str, Any]):
    """Traite un job activé selon son type."""
    job_key = str(job.get("jobKey", job.get("key", "")))
    job_type = job.get("type", "")
    retries = int(job.get("retries", 3))
    variables = job.get("variables", {})
    
    logging.info(f"Traitement du job {job_key} (type: {job_type})...")
    
    try:
        if job_type == "health-check":
            output_vars = handle_health_check(variables)
            complete_job(camunda_url, job_key, output_vars)
        elif job_type == "vault-note":
            output_vars = handle_vault_note(variables)
            complete_job(camunda_url, job_key, output_vars)
        else:
            logging.warning(f"Type de job non supporté: {job_type}")
            fail_job(camunda_url, job_key, retries, f"Unknown job type: {job_type}")
    except Exception as e:
        logging.exception(f"Exception lors du traitement du job {job_key}: {e}")
        fail_job(camunda_url, job_key, retries, str(e))


def run_loop(camunda_url: str = DEFAULT_CAMUNDA_URL):
    logging.info(f"Démarrage du worker {WORKER_NAME} sur {camunda_url}...")
    logging.info(f"Job types écoutés: {JOB_TYPES}")
    logging.info("waiting for jobs")
    
    try:
        while True:
            for j_type in JOB_TYPES:
                jobs = activate_jobs(camunda_url, j_type, timeout=30000, request_timeout=3000)
                for job in jobs:
                    process_job(camunda_url, job)
            time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info("Arrêt du worker par KeyboardInterrupt.")


def run_once(
    *,
    night_date: str,
    vault_dir: str,
    topology_url: str,
    snapshot_path: str = "",
) -> Dict[str, Any]:
    """Mode dégradé : sonde + note Obsidian sans job Camunda."""
    variables = {
        "nightDate": night_date,
        "vaultDir": vault_dir,
        "topologyUrl": topology_url,
    }
    if snapshot_path:
        variables["snapshotPath"] = snapshot_path
    sante = handle_health_check(variables)
    sante.update(nightDate=night_date, vaultDir=vault_dir)
    note = handle_vault_note(sante)
    logging.info(
        "once status=%s degraded=%s note=%s",
        sante.get("healthStatus"),
        sante.get("degradedComponents") or "aucun",
        note.get("notePath"),
    )
    return {**sante, **note}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camunda stdlib worker")
    parser.add_argument("--camunda-url", default=DEFAULT_CAMUNDA_URL, help="URL REST Camunda v2")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Sonde et écrit la note sans attendre un job Camunda",
    )
    parser.add_argument("--night-date", default=time.strftime("%Y-%m-%d"))
    parser.add_argument(
        "--vault-dir",
        default=str(dossier_notes_par_defaut()),
    )
    parser.add_argument(
        "--topology-url",
        default="http://127.0.0.1:8088/v2/topology",
    )
    parser.add_argument("--snapshot", default="", help="JSON lu par Presence (--sante)")
    args = parser.parse_args()

    if args.once:
        run_once(
            night_date=args.night_date,
            vault_dir=args.vault_dir,
            topology_url=args.topology_url,
            snapshot_path=args.snapshot,
        )
    else:
        run_loop(args.camunda_url)
