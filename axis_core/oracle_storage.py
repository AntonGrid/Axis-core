# axis_core/oracle_storage.py
from typing import Dict, Any

# Global in-memory storage for attestations and requests
_ATTESTATIONS: Dict[str, Dict[str, Any]] = {}
_REQUESTS: Dict[str, Dict[str, Any]] = {}

#: Nonces already seen per device (replay protection).
_USED_NONCES: Dict[str, set] = {}


def has_nonce(device_id: str, nonce: str) -> bool:
    """Return True if ``nonce`` was already used by ``device_id``."""
    return nonce in _USED_NONCES.get(device_id, set())


def record_nonce(device_id: str, nonce: str) -> None:
    """Mark ``nonce`` as used by ``device_id``."""
    _USED_NONCES.setdefault(device_id, set()).add(nonce)


class InMemoryOracleStorage:
    """
    Simple in-memory implementation for storing Oracle attestations.
    Used in tests as a stub for persistent storage.
    """

    def __init__(self) -> None:
        self._store = {}

    def store_attestation(self, attestation: dict) -> None:
        """
        Store an attestation by its identifier.
        Requires 'attestation_id' field in the attestation dict.
        """
        attestation_id = attestation.get("attestation_id")
        if not attestation_id:
            raise KeyError("Missing attestation_id in attestation")
        self._store[attestation_id] = attestation

    def get_attestation(self, attestation_id: str):
        """
        Return an attestation by ID, or None if not found.
        """
        return self._store.get(attestation_id)
