# app/oracle_storage.py

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
