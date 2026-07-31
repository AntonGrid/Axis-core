from fastapi.testclient import TestClient

from axis_core.main import app

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
