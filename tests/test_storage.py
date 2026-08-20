"""Storage backend tests.

- Unit tests for the in-memory backend (contract + behavior).
- Optional integration tests for Redis/PostgreSQL backends, skipped unless
  ``REDIS_URL`` / ``DATABASE_URL`` are provided (run them via docker compose).
"""
import os

import pytest

from axis_core.storage.factory import get_backend, reset_backend
from axis_core.storage.memory import MemoryBackend
from axis_core.storage.models import RegisteredDevice

_DEVICE = RegisteredDevice(
    device_id="dev_1234567890abcdef",
    public_key="a" * 44,
    manifest_ref="manifest:test-1",
    bootstrap_policy={"allowed": True, "max_power_kw": 3.5},
)


def _fresh_memory() -> MemoryBackend:
    backend = MemoryBackend()
    backend.reset()
    return backend


def test_memory_device_roundtrip():
    backend = _fresh_memory()
    assert backend.get_device(_DEVICE.device_id) is None
    backend.put_device(_DEVICE)
    got = backend.get_device(_DEVICE.device_id)
    assert got is not None
    assert got.device_id == _DEVICE.device_id
    assert got.public_key == _DEVICE.public_key
    assert got.manifest_ref == _DEVICE.manifest_ref
    assert got.bootstrap_policy == _DEVICE.bootstrap_policy


def test_memory_device_upsert():
    backend = _fresh_memory()
    backend.put_device(_DEVICE)
    updated = RegisteredDevice(
        device_id=_DEVICE.device_id,
        public_key=_DEVICE.public_key,
        manifest_ref="manifest:test-2",
        bootstrap_policy={"allowed": False},
    )
    backend.put_device(updated)
    assert backend.get_device(_DEVICE.device_id).manifest_ref == "manifest:test-2"


def test_memory_nonce_replay():
    backend = _fresh_memory()
    assert backend.has_nonce("dev_x", "n1") is False
    backend.record_nonce("dev_x", "n1")
    assert backend.has_nonce("dev_x", "n1") is True
    # nonce scoped per device
    assert backend.has_nonce("dev_y", "n1") is False


def test_memory_reset_clears_state():
    backend = _fresh_memory()
    backend.put_device(_DEVICE)
    backend.record_nonce(_DEVICE.device_id, "n1")
    backend.reset()
    assert backend.get_device(_DEVICE.device_id) is None
    assert backend.has_nonce(_DEVICE.device_id, "n1") is False


def test_factory_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("AXIS_STORAGE_BACKEND", raising=False)
    reset_backend()
    try:
        assert isinstance(get_backend(), MemoryBackend)
    finally:
        reset_backend()


def test_factory_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("AXIS_STORAGE_BACKEND", "bogus")
    reset_backend()
    try:
        with pytest.raises(ValueError):
            get_backend()
    finally:
        reset_backend()


@pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL not set")
def test_redis_backend_integration():
    from axis_core.storage.redis_backend import RedisBackend

    backend = RedisBackend.from_env()
    backend.reset()
    backend.put_device(_DEVICE)
    assert backend.get_device(_DEVICE.device_id).device_id == _DEVICE.device_id
    backend.record_nonce(_DEVICE.device_id, "n1")
    assert backend.has_nonce(_DEVICE.device_id, "n1") is True


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_postgres_backend_integration():
    from axis_core.storage.postgres_backend import PostgresBackend

    backend = PostgresBackend.from_env()
    backend.put_device(_DEVICE)
    assert backend.get_device(_DEVICE.device_id).manifest_ref == _DEVICE.manifest_ref
    backend.record_nonce(_DEVICE.device_id, "n1")
    assert backend.has_nonce(_DEVICE.device_id, "n1") is True
