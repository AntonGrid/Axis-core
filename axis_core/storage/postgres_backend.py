"""PostgreSQL storage backend: device registry (+ nonce ledger).

Requires the ``psycopg`` package (lazy-imported) and ``DATABASE_URL``.
Tables are created with ``CREATE TABLE IF NOT EXISTS`` on startup; no
migration framework is used.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from axis_core.storage.base import StorageBackend
from axis_core.storage.models import (
    RegisteredDevice,
    device_from_dict,
    device_to_dict,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS axis_devices (
    device_id       TEXT PRIMARY KEY,
    public_key      TEXT NOT NULL,
    manifest_ref    TEXT NOT NULL,
    bootstrap_policy JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS axis_nonces (
    device_id TEXT NOT NULL,
    nonce     TEXT NOT NULL,
    seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, nonce)
);
CREATE TABLE IF NOT EXISTS axis_attestations (
    attestation_id TEXT PRIMARY KEY,
    data           JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS axis_requests (
    request_id  TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class PostgresBackend(StorageBackend):
    def __init__(self, conn) -> None:
        self._conn = conn
        with self._conn.cursor() as cur:
            cur.execute(_SCHEMA)
        self._conn.commit()

    @classmethod
    def from_env(cls) -> "PostgresBackend":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is required for AXIS_STORAGE_BACKEND=postgres/hybrid"
            )
        try:
            import psycopg
        except ImportError as e:  # pragma: no cover - env-specific
            raise RuntimeError(
                "psycopg is not installed; add `psycopg[binary]` from "
                "requirements-storage.txt"
            ) from e
        return cls(psycopg.connect(url))

    # -- devices ---------------------------------------------------------
    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT public_key, manifest_ref, bootstrap_policy FROM axis_devices "
                "WHERE device_id = %s",
                (device_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return RegisteredDevice(
            device_id=device_id,
            public_key=row[0],
            manifest_ref=row[1],
            bootstrap_policy=row[2],
        )

    def put_device(self, device: RegisteredDevice) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO axis_devices (device_id, public_key, manifest_ref, "
                "bootstrap_policy) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (device_id) DO UPDATE SET public_key = EXCLUDED.public_key, "
                "manifest_ref = EXCLUDED.manifest_ref, "
                "bootstrap_policy = EXCLUDED.bootstrap_policy",
                (
                    device.device_id,
                    device.public_key,
                    device.manifest_ref,
                    json.dumps(device_to_dict(device)["bootstrap_policy"]),
                ),
            )
        self._conn.commit()

    # -- nonces ----------------------------------------------------------
    def has_nonce(self, device_id: str, nonce: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM axis_nonces WHERE device_id = %s AND nonce = %s",
                (device_id, nonce),
            )
            return cur.fetchone() is not None

    def record_nonce(self, device_id: str, nonce: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO axis_nonces (device_id, nonce) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (device_id, nonce),
            )
        self._conn.commit()

    # -- attestations -----------------------------------------------------
    def put_attestation(self, attestation_id: str, attestation) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO axis_attestations (attestation_id, data) VALUES (%s, %s) "
                "ON CONFLICT (attestation_id) DO UPDATE SET data = EXCLUDED.data",
                (attestation_id, json.dumps(attestation)),
            )
        self._conn.commit()

    def get_attestation(self, attestation_id: str):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM axis_attestations WHERE attestation_id = %s",
                (attestation_id,),
            )
            row = cur.fetchone()
        return None if row is None else row[0]

    def all_attestations(self) -> dict:
        with self._conn.cursor() as cur:
            cur.execute("SELECT attestation_id, data FROM axis_attestations")
            rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}

    # -- oracle requests --------------------------------------------------
    def put_request(self, request_id: str, request) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO axis_requests (request_id, data) VALUES (%s, %s) "
                "ON CONFLICT (request_id) DO UPDATE SET data = EXCLUDED.data",
                (request_id, json.dumps(request)),
            )
        self._conn.commit()

    def get_request(self, request_id: str):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM axis_requests WHERE request_id = %s",
                (request_id,),
            )
            row = cur.fetchone()
        return None if row is None else row[0]

    def all_requests(self) -> dict:
        with self._conn.cursor() as cur:
            cur.execute("SELECT request_id, data FROM axis_requests")
            rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}

    def reset(self) -> None:
        # Never wipe a shared database on reset; tests use ``memory``.
        pass
