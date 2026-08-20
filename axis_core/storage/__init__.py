"""Storage layer for Axis Core.

Provides a small storage abstraction so the core can run in-memory (default,
used by tests) or with production persistence:

- ``memory``   — in-process dicts (default; zero dependencies);
- ``redis``    — nonce replay ledger + device registry in Redis;
- ``postgres`` — device registry (+ nonce ledger) in PostgreSQL;
- ``hybrid``   — nonces in Redis, devices in PostgreSQL.

Select via ``AXIS_STORAGE_BACKEND``. ``REDIS_URL`` / ``DATABASE_URL`` are read
from the environment (see ``factory.py``).
"""
from axis_core.storage.factory import get_backend, reset_backend

__all__ = ["get_backend", "reset_backend"]
