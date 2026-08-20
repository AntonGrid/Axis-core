"""In-memory storage backend (default, zero dependencies)."""
from __future__ import annotations

from typing import Dict, Optional, Set

from axis_core.storage.base import StorageBackend
from axis_core.storage.models import RegisteredDevice


class MemoryBackend(StorageBackend):
    """Process-local dicts. Suitable for tests and single-worker demos."""

    def __init__(self) -> None:
        self._devices: Dict[str, RegisteredDevice] = {}
        self._nonces: Dict[str, Set[str]] = {}

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        return self._devices.get(device_id)

    def put_device(self, device: RegisteredDevice) -> None:
        self._devices[device.device_id] = device

    def has_nonce(self, device_id: str, nonce: str) -> bool:
        return nonce in self._nonces.get(device_id, set())

    def record_nonce(self, device_id: str, nonce: str) -> None:
        self._nonces.setdefault(device_id, set()).add(nonce)

    def reset(self) -> None:
        self._devices.clear()
        self._nonces.clear()
