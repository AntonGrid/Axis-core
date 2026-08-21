"""Storage backend interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from axis_core.storage.models import RegisteredDevice


class StorageBackend(ABC):
    """Minimal persistence contract used by the Axis Core runtime.

    Implementations MUST be safe for concurrent workers where applicable and
    MUST provide ``reset()`` so the test suite can isolate state.
    """

    # -- devices ---------------------------------------------------------

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        """Return the registered device or ``None``."""

    @abstractmethod
    def put_device(self, device: RegisteredDevice) -> None:
        """Store (upsert) a registered device."""

    # -- nonces ----------------------------------------------------------

    @abstractmethod
    def has_nonce(self, device_id: str, nonce: str) -> bool:
        """Return True if ``nonce`` was already used by ``device_id``."""

    @abstractmethod
    def record_nonce(self, device_id: str, nonce: str) -> None:
        """Mark ``nonce`` as used by ``device_id`` (idempotent)."""

    # -- attestations ----------------------------------------------------

    @abstractmethod
    def put_attestation(self, attestation_id: str, attestation: Dict[str, Any]) -> None:
        """Store (upsert) an attestation document."""

    @abstractmethod
    def get_attestation(self, attestation_id: str) -> Optional[Dict[str, Any]]:
        """Return an attestation or ``None``."""

    @abstractmethod
    def all_attestations(self) -> Dict[str, Dict[str, Any]]:
        """Return all stored attestations keyed by ``attestation_id``."""

    # -- oracle requests -------------------------------------------------

    @abstractmethod
    def put_request(self, request_id: str, request: Dict[str, Any]) -> None:
        """Store (upsert) an oracle request document."""

    @abstractmethod
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Return an oracle request or ``None``."""

    @abstractmethod
    def all_requests(self) -> Dict[str, Dict[str, Any]]:
        """Return all stored oracle requests keyed by ``request_id``."""

    # -- lifecycle -------------------------------------------------------

    @abstractmethod
    def reset(self) -> None:
        """Drop all state (used by tests; no-op is acceptable for durable
        backends that should not be wiped in production)."""

