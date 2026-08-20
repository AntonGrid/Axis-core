import base64

from fastapi.testclient import TestClient

from axis_core.main import app

from tests.signature_helpers import build_signed_proof, make_registered_device, now_iso8601_z

client = TestClient(app)


def test_attest_bad_device_id():
    proof = {
        "device_id": "BAD_ID",
        "nonce": "abc12345xyz",
        "timestamp": "2026-07-25T19:00:00Z",
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }
    resp = client.post("/provisioning/attest", json=proof)
    assert resp.status_code == 400
    body = resp.json()
    # /provisioning/attest returns detail as an object
    detail = body["detail"]
    assert detail["message"] == "Invalid DeviceProof"
    assert "does not match" in detail["error"]


def test_oracle_attest_invalid_missing_field():
    att = {
        # "attestation_id" missing
        "device_id": "dev_9e9c644e1580a83b",
        "proof": {},
        "decision": {"allowed": True, "reason": "ok"},
        "oracle_id": "oracle_main_1",
        "issued_at": "2026-07-25T19:05:00Z",
        "oracle_signature": "cafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebabe",
    }
    resp = client.post("/oracle/attest", json=att)
    assert resp.status_code == 400
    body = resp.json()
    # /oracle/attest returns detail as a "Validation error: ..." string
    assert "Validation error" in body["detail"]
    assert "Additional properties are not allowed" in body["detail"]


def test_oracle_attest_mode1_rejects_forged_attestation():
    # A full "legacy" attestation with a forged device signature must not be
    # accepted: Mode 1 re-verifies the embedded proof through the decision
    # pipeline and rejects unverifiable proofs with 403.
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_mode1_123456", now_iso8601_z(), 2.5)

    raw = bytearray(base64.b64decode(proof["signature"]))
    raw[0] ^= 0xFF
    proof["signature"] = base64.b64encode(bytes(raw)).decode("ascii")

    forged = {
        "schema_version": "1.0",
        "attestation_id": "att_forged_1234567890",
        "device_id": device_id,
        "proof": proof,
        "decision": {"allowed": True, "reason": "ok", "max_power_kw": 2.5},
        "oracle_id": "oracle_main_1",
        "issued_at": now_iso8601_z(),
        "oracle_signature": "cafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebabe",
    }

    resp = client.post("/oracle/attest", json=forged)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == "signature_invalid"


def test_oracle_attest_mode1_accepts_valid_attestation():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce_mode1_ok_1234", now_iso8601_z(), 2.5)

    attestation = {
        "schema_version": "1.0",
        "attestation_id": "att_valid_1234567890",
        "device_id": device_id,
        "proof": proof,
        "decision": {"allowed": True, "reason": "ok", "max_power_kw": 2.5},
        "oracle_id": "oracle_main_1",
        "issued_at": now_iso8601_z(),
        "oracle_signature": "cafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebabe",
    }

    resp = client.post("/oracle/attest", json=attestation)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "received"
    assert body["attestation_id"] == "att_valid_1234567890"
