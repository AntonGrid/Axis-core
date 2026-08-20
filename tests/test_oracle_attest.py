import base64
import os

from fastapi.testclient import TestClient

from axis_core.main import app
from axis_core.oracle_keys import encode_oracle_public_key, verify_oracle_signature
from axis_core.signature_utils import generate_device_key

from tests.signature_helpers import (
    build_signed_proof,
    iso8601_z_offset_seconds,
    make_registered_device,
    now_iso8601_z,
)

client = TestClient(app)


def test_oracle_attest_request_ok():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "abc12345xyz", now_iso8601_z(), 2.5)

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200

    body = resp.json()
    assert body["device_id"] == device_id
    assert "attestation_id" in body

    decision = body["decision"]
    assert decision["allowed"] is True
    assert decision["reason"] == "ok"
    assert decision["max_power_kw"] == 2.5


def test_oracle_attest_stored_attestation_has_real_oracle_signature():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_sig_1234567", now_iso8601_z(), 2.5)

    resp = client.post("/oracle/attest", json=proof)
    att_id = resp.json()["attestation_id"]

    stored = client.get(f"/oracle/attestations/{att_id}").json()
    assert stored["oracle_signature"] != "mock-oracle-signature"

    oracle_public_key_b64 = encode_oracle_public_key(os.environ["ORACLE_SECRET_KEY"])
    assert verify_oracle_signature(stored, oracle_public_key_b64)


def test_oracle_attest_request_invalid_schema():
    # Missing required field 'signature'
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": now_iso8601_z(),
        "algo": "ed25519",
        "payload": {"max_power_kw": 2.5},
        # "signature": ...
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400

    body = resp.json()
    assert "Validation error" in body["detail"]
    assert "required property" in body["detail"]


def test_oracle_attest_missing_timestamp():
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "algo": "ed25519",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400
    assert "required property" in resp.json()["detail"]


def test_oracle_attest_missing_nonce():
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "timestamp": now_iso8601_z(),
        "algo": "ed25519",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400
    assert "required property" in resp.json()["detail"]


def test_oracle_attest_request_invalid_timestamp():
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        # Invalid format: missing trailing 'Z'
        "timestamp": "2026-07-25T19:05:00",
        "algo": "ed25519",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 400
    assert "must end with 'Z'" in resp.json()["detail"]


def test_oracle_attest_stale_timestamp():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(
        key, device_id, "nonce_stale_12345", iso8601_z_offset_seconds(-1000), 2.5
    )

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "stale_timestamp"


def test_oracle_attest_future_timestamp():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(
        key, device_id, "nonce_future_12345", iso8601_z_offset_seconds(400), 2.5
    )

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "future_timestamp"


def test_oracle_attest_nonce_replay():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_replay_12345", now_iso8601_z(), 2.5)

    first = client.post("/oracle/attest", json=proof)
    assert first.status_code == 200
    assert first.json()["decision"]["allowed"] is True

    # Same nonce for the same device -> replay rejected.
    second = client.post("/oracle/attest", json=proof)
    assert second.status_code == 200
    decision = second.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "nonce_replay"


def test_oracle_attest_denied_when_power_too_high():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_high_12345", now_iso8601_z(), 10.0)

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    body = resp.json()

    decision = body["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "max_power_exceeded"
    assert decision["max_power_kw"] == 5.0
    assert decision["limit_kw"] == 5.0


def test_oracle_attest_unregistered_device():
    key = generate_device_key()
    # A device_id matching the schema pattern that was never registered.
    device_id = "dev_0123456789abcdef"
    proof = build_signed_proof(key, device_id, "nonce_unreg_1234", now_iso8601_z(), 2.5)

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "device_not_registered"


def test_oracle_attest_invalid_signature():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_bad_sig_12", now_iso8601_z(), 2.5)

    # Tamper with the signature: flip one byte.
    raw = bytearray(base64.b64decode(proof["signature"]))
    raw[0] ^= 0xFF
    proof["signature"] = base64.b64encode(bytes(raw)).decode("ascii")

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "signature_invalid"


def test_oracle_attest_signature_from_different_key():
    key, device_id = make_registered_device(client)
    other_key = generate_device_key()
    # Signed by a key that is NOT the registered one.
    proof = build_signed_proof(other_key, device_id, "nonce_other_key", now_iso8601_z(), 2.5)

    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "signature_invalid"


def test_oracle_attest_mock_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AXIS_ALLOW_MOCK", raising=False)
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": now_iso8601_z(),
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "mock_disabled"


def test_oracle_attest_mock_allowed_with_env(monkeypatch):
    monkeypatch.setenv("AXIS_ALLOW_MOCK", "1")
    payload = {
        "device_id": "dev_9e9c644e1580a83b",
        "nonce": "abc12345xyz",
        "timestamp": now_iso8601_z(),
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }

    resp = client.post("/oracle/attest", json=payload)
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is True
    assert decision["reason"] == "ok"
