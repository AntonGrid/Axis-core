"""Storage backend interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from axis_core.storage.models import RegisteredDevice


class StorageBackend(ABC):
    """Minimal persistence contract used by the Axis Core runtime.

    Implementations MUST be safe for concurrent workers where applicable and
    MUST provide ``reset()`` so the test suite can isolate state.
    """

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        """Return the registered device or ``None``."""

    @abstractmethod
    def put_device(self, device: RegisteredDevice) -> None:
        """Store (upsert) a registered device."""

    @abstractmethod
    def has_nonce(self, device_id: str, nonce: str) -> bool:
        """Return True if ``nonce`` was already used by ``device_id``."""

    @abstractmethod
    def record_nonce(self, device_id: str, nonce: str) -> None:
        """Mark ``nonce`` as used by ``device_id`` (idempotent)."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all state (used by tests; no-op is acceptable for durable
        backends that should not be wiped in production)."""
