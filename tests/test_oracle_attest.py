from datetime import datetime, timezone

import json
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _now_utc_no_microseconds() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_attest_happy_path():
    now = _now_utc_no_microseconds()
    proof_timestamp = now.isoformat().replace("+00:00", "Z")

    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": proof_timestamp,
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["device_id"] == payload["device_id"]
    assert "attestation_id" in data
    assert "decision" in data
    assert data["decision"]["allowed"] is True
    assert data["decision"]["max_power_kw"] == 2.5


def test_attest_schema_validation_error_missing_required():
    now = _now_utc_no_microseconds()
    proof_timestamp = now.isoformat().replace("+00:00", "Z")

    # Нет поля "signature"
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": proof_timestamp,
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"] == "schema_validation_error"
    assert "signature" in json.dumps(data["detail"]["message"])


def test_attest_schema_validation_error_invalid_timestamp():
    # Некорректный формат timestamp
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": "invalid-timestamp",
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"] == "schema_validation_error"
    assert "timestamp" in json.dumps(data["detail"]["message"])
