"""In-memory storage backend (default, zero dependencies)."""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from axis_core.storage.base import StorageBackend
from axis_core.storage.models import RegisteredDevice


class MemoryBackend(StorageBackend):
    """Process-local dicts. Suitable for tests and single-worker demos."""

    def __init__(self) -> None:
        self._devices: Dict[str, RegisteredDevice] = {}
        self._nonces: Dict[str, Set[str]] = {}
        self._attestations: Dict[str, Dict[str, Any]] = {}
        self._requests: Dict[str, Dict[str, Any]] = {}

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        return self._devices.get(device_id)

    def put_device(self, device: RegisteredDevice) -> None:
        self._devices[device.device_id] = device

    def has_nonce(self, device_id: str, nonce: str) -> bool:
        return nonce in self._nonces.get(device_id, set())

    def record_nonce(self, device_id: str, nonce: str) -> None:
        self._nonces.setdefault(device_id, set()).add(nonce)

    def put_attestation(self, attestation_id: str, attestation: Dict[str, Any]) -> None:
        self._attestations[attestation_id] = attestation

    def get_attestation(self, attestation_id: str) -> Optional[Dict[str, Any]]:
        return self._attestations.get(attestation_id)

    def all_attestations(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._attestations)

    def put_request(self, request_id: str, request: Dict[str, Any]) -> None:
        self._requests[request_id] = request

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self._requests.get(request_id)

    def all_requests(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._requests)

    def reset(self) -> None:
        self._devices.clear()
        self._nonces.clear()
        self._attestations.clear()
        self._requests.clear()
