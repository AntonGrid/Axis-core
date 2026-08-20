from fastapi.testclient import TestClient

from axis_core.main import app
from axis_core.signature_utils import encode_public_key, generate_device_key

from tests.signature_helpers import register_device


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_provisioning_and_registry():
    key = generate_device_key()
    device_id = register_device(client, encode_public_key(key), signing_key=key)

    reg_resp = client.get(f"/registry/devices/{device_id}")
    assert reg_resp.status_code == 200
    rec = reg_resp.json()
    assert rec["device_id"] == device_id

