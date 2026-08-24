"""
GATE: Hash-chained append-only audit log.

Records all capability negotiation, BRAIN calls, and permission decisions.
"""
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AuditLog:
    """Hash-chained audit log for MOTHER operations."""

    def __init__(self, log_path: str = "logs/audit.jsonl"):
        """
        Initialize audit log.

        Args:
            log_path: path to append-only log file
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_hash = None
        self._load_last_hash()
        logger.info(f"AuditLog initialized: {log_path}")

    def _load_last_hash(self):
        """Load the last entry's hash to continue chain."""
        if self.log_path.exists():
            try:
                with open(self.log_path, "r") as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = json.loads(lines[-1])
                        self.last_hash = last_entry.get("hash")
                        logger.info(f"Loaded audit chain from {len(lines)} entries")
            except Exception as e:
                logger.warning(f"Could not load audit log: {e}")
                self.last_hash = None

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of entry data."""
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def log(
        self,
        action: str,
        params: Dict[str, Any],
        result: str = "success",
        caller: str = "unknown",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log an action to the audit trail.

        Args:
            action: action name (e.g., brain_query, capability_negotiation)
            params: parameters (sanitized — no secrets)
            result: success, error, or other status
            caller: which component initiated this
            user_id: optional user identifier

        Returns:
            logged entry
        """
        entry_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "params": params,
            "result": result,
            "caller": caller,
            "user_id": user_id or "anonymous",
            "prev_hash": self.last_hash
        }

        # Compute hash of this entry
        entry_hash = self._compute_hash(entry_data)
        entry_data["hash"] = entry_hash
        self.last_hash = entry_hash

        # Append to log
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry_data) + "\n")
                f.flush()
            logger.debug(f"Audit log: {action} → {result}")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        return entry_data

    async def get_entries(self, limit: int = 100) -> list:
        """
        Retrieve audit log entries (most recent first).

        Args:
            limit: maximum number of entries

        Returns:
            list of entries
        """
        if not self.log_path.exists():
            return []

        try:
            with open(self.log_path, "r") as f:
                entries = [json.loads(line) for line in f.readlines()]
            return entries[-limit:] if limit else entries

        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []

    async def verify_chain(self) -> bool:
        """
        Verify integrity of audit chain (hash links).

        Returns:
            True if chain is valid, False if tampering detected
        """
        if not self.log_path.exists():
            return True

        try:
            with open(self.log_path, "r") as f:
                entries = [json.loads(line) for line in f.readlines()]

            prev_hash = None
            for i, entry in enumerate(entries):
                # Check that prev_hash matches previous entry's hash
                if i > 0 and entry.get("prev_hash") != prev_hash:
                    logger.error(f"Chain broken at entry {i}")
                    return False

                # Check that entry's hash is correct
                stored_hash = entry.pop("hash", None)
                computed_hash = self._compute_hash(entry)
                if stored_hash != computed_hash:
                    logger.error(f"Hash mismatch at entry {i}")
                    return False

                prev_hash = stored_hash

            logger.info(f"Audit chain verified: {len(entries)} entries")
            return True

        except Exception as e:
            logger.error(f"Chain verification error: {e}")
            return False
