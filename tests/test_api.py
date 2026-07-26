from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_and_get_device():
    # Register device
    resp = client.post("/provisioning/register", json={"public_key": "test-public-key-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "device_id" in data
    device_id = data["device_id"]

    # Get from registry
    resp2 = client.get(f"/registry/devices/{device_id}")
    assert resp2.status_code == 200
    record = resp2.json()
    assert record["device_id"] == device_id
    assert record["public_key"] == "test-public-key-123"


def test_attest_ok():
    # First register device
    resp = client.post("/provisioning/register", json={"public_key": "test-public-key-456"})
    assert resp.status_code == 200
    device_id = resp.json()["device_id"]

    # Send valid attest
    proof = {
        "device_id": device_id,
        "nonce": "abc12345xyz",
        "timestamp": "2026-07-25T19:00:00Z",
        "algo": "mock",
        "payload": {"max_power_kw": 2.5},
        "signature": "deadbeef" * 8,
    }
    resp2 = client.post("/provisioning/attest", json=proof)
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["status"] == "ok"
    assert body["device_id"] == device_id
    assert body["decision"]["allowed"] is True


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
    assert body["detail"]["message"] == "Invalid DeviceProof"
    assert body["detail"]["path"] == ["device_id"]
