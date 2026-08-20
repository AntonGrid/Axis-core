"""Redis storage backend: nonce replay ledger + device registry.

Requires the ``redis`` package (lazy-imported) and ``REDIS_URL``.
Nonces are stored with ``SET NX EX`` and a TTL equal to
``MAX_PROOF_AGE_SECONDS`` so the ledger is self-cleaning.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from axis_core.config import MAX_PROOF_AGE_SECONDS
from axis_core.storage.base import StorageBackend
from axis_core.storage.models import (
    RegisteredDevice,
    device_from_dict,
    device_to_dict,
)


class RedisBackend(StorageBackend):
    def __init__(self, client, *, ttl: int = MAX_PROOF_AGE_SECONDS) -> None:
        self._r = client
        self._ttl = ttl

    @classmethod
    def from_env(cls) -> "RedisBackend":
        url = os.environ.get("REDIS_URL")
        if not url:
            raise RuntimeError(
                "REDIS_URL is required for AXIS_STORAGE_BACKEND=redis/hybrid"
            )
        try:
            import redis  # lazy: optional dependency
        except ImportError as e:  # pragma: no cover - env-specific
            raise RuntimeError(
                "redis package is not installed; add `redis` from "
                "requirements-storage.txt"
            ) from e
        return cls(redis.from_url(url, decode_responses=True))

    # -- devices ---------------------------------------------------------
    def _device_key(self, device_id: str) -> str:
        return f"axis:device:{device_id}"

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        raw = self._r.get(self._device_key(device_id))
        if raw is None:
            return None
        return device_from_dict(json.loads(raw))

    def put_device(self, device: RegisteredDevice) -> None:
        self._r.set(
            self._device_key(device.device_id),
            json.dumps(device_to_dict(device)),
        )

    # -- nonces ----------------------------------------------------------
    def _nonce_key(self, device_id: str, nonce: str) -> str:
        return f"axis:nonce:{device_id}:{nonce}"

    def has_nonce(self, device_id: str, nonce: str) -> bool:
        return self._r.exists(self._nonce_key(device_id, nonce)) > 0

    def record_nonce(self, device_id: str, nonce: str) -> None:
        self._r.set(self._nonce_key(device_id, nonce), "1", nx=True, ex=self._ttl)

    def reset(self) -> None:
        # Never wipe a shared Redis on reset; tests use ``memory``.
        pass
