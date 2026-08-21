"""Backend factory: picks a storage backend from the environment.

``AXIS_STORAGE_BACKEND``:
- ``memory``   (default) — in-process; zero dependencies;
- ``redis``    — nonces + devices in Redis (requires ``REDIS_URL``);
- ``postgres`` — devices + nonces in PostgreSQL (requires ``DATABASE_URL``);
- ``hybrid``   — nonces in Redis, devices in PostgreSQL.
"""
from __future__ import annotations

import os
from typing import Optional

from axis_core.storage.base import StorageBackend
from axis_core.storage.memory import MemoryBackend

_BACKEND: Optional[StorageBackend] = None


class HybridBackend(StorageBackend):
    """Nonces in Redis, devices in PostgreSQL."""

    def __init__(self, redis_backend: StorageBackend, postgres_backend: StorageBackend) -> None:
        self._redis = redis_backend
        self._postgres = postgres_backend

    def get_device(self, device_id: str):
        return self._postgres.get_device(device_id)

    def put_device(self, device) -> None:
        self._postgres.put_device(device)

    def has_nonce(self, device_id: str, nonce: str) -> bool:
        return self._redis.has_nonce(device_id, nonce)

    def record_nonce(self, device_id: str, nonce: str) -> None:
        self._redis.record_nonce(device_id, nonce)

    def put_attestation(self, attestation_id: str, attestation) -> None:
        self._postgres.put_attestation(attestation_id, attestation)

    def get_attestation(self, attestation_id: str):
        return self._postgres.get_attestation(attestation_id)

    def all_attestations(self) -> dict:
        return self._postgres.all_attestations()

    def put_request(self, request_id: str, request) -> None:
        self._postgres.put_request(request_id, request)

    def get_request(self, request_id: str):
        return self._postgres.get_request(request_id)

    def all_requests(self) -> dict:
        return self._postgres.all_requests()

    def reset(self) -> None:
        self._redis.reset()
        self._postgres.reset()


def _build(mode: str) -> StorageBackend:
    if mode == "memory":
        return MemoryBackend()
    if mode == "redis":
        from axis_core.storage.redis_backend import RedisBackend

        return RedisBackend.from_env()
    if mode == "postgres":
        from axis_core.storage.postgres_backend import PostgresBackend

        return PostgresBackend.from_env()
    if mode == "hybrid":
        from axis_core.storage.postgres_backend import PostgresBackend
        from axis_core.storage.redis_backend import RedisBackend

        return HybridBackend(RedisBackend.from_env(), PostgresBackend.from_env())
    raise ValueError(
        f"Unknown AXIS_STORAGE_BACKEND={mode!r}; expected one of "
        "memory | redis | postgres | hybrid"
    )


def get_backend() -> StorageBackend:
    """Return the process-wide storage backend (cached)."""
    global _BACKEND
    if _BACKEND is None:
        mode = os.environ.get("AXIS_STORAGE_BACKEND", "memory").strip().lower()
        _BACKEND = _build(mode)
    return _BACKEND


def reset_backend() -> None:
    """Drop the cached backend so the next ``get_backend()`` rebuilds it.

    Used by the test suite to isolate state between tests.
    """
    global _BACKEND
    _BACKEND = None
