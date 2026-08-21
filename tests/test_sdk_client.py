"""SDK client tests.

The transport is injected (httpx.MockTransport) so the suite needs no network.
It exercises the full device flow through the reference HTTP API:

register (proof-of-possession) → submit proof → attestation → envelope.
"""
import base64

import httpx
import nacl.signing

from axis_core.sdk import AxisClient, HttpError
from axis_core.signature_utils import encode_public_key
from axis_core.wire import MessageType


def _mock_transport(routes):
    """Build a fake transport answering ``routes``: ``{(method, path): json}``."""

    def transport(method, url, json=None):
        for (m, path), data in routes.items():
            if method == m and url.endswith(path):
                return httpx.Response(200, json=data)
        return httpx.Response(404, json={"error": "not found"})

    return transport


def _device_key():
    return nacl.signing.SigningKey.generate()


def test_register_submits_proof_of_possession():
    key = _device_key()
    pub = encode_public_key(key)
    calls = []

    def transport(method, url, json=None):
        calls.append((method, url, json))
        if method == "POST" and url.endswith("/provisioning/register"):
            assert json["public_key"] == pub
            assert json["signature"]  # proof-of-possession signed locally
            return httpx.Response(200, json={"device_id": "dev_registered", "manifest_ref": "m1", "bootstrap_policy": {}})
        return httpx.Response(404, json={"error": "not found"})

    client = AxisClient("http://127.0.0.1:8000", transport=transport)
    result = client.register(pub, signing_key=key)
    assert result["device_id"] == "dev_registered"


def test_submit_proof_and_read_attestation():
    key = _device_key()
    pub = encode_public_key(key)
    device_id = "dev_0123456789abcdef"

    routes = {
        ("POST", "/provisioning/register"): {"device_id": device_id, "manifest_ref": "m1", "bootstrap_policy": {}},
        ("POST", "/oracle/attest"): {"device_id": device_id, "attestation_id": "att_1", "decision": {"allowed": True, "reason": "ok"}, "oracle_id": "oracle_main_1"},
        ("GET", "/oracle/attestations?limit=10&offset=0"): {"total": 1, "limit": 10, "offset": 0, "attestations": [{"attestation_id": "att_1"}]},
        ("GET", f"/registry/devices/{device_id}"): {"device_id": device_id, "public_key": pub, "lifecycle_state": "provisioned"},
    }

    client = AxisClient("http://127.0.0.1:8000", transport=_mock_transport(routes))

    proof = client.build_proof(
        device_id, {"max_power_kw": 2.5, "timestamp": "2026-08-21T12:00:00Z"}, key, nonce="n-1"
    )
    assert proof["signature"]

    att = client.submit_proof(proof)
    assert att["decision"]["allowed"] is True

    listing = client.attestations(limit=10, offset=0)
    assert listing["total"] == 1

    status = client.device_status(device_id)
    assert status["lifecycle_state"] == "provisioned"


def test_envelope_roundtrip_through_sdk():
    key = _device_key()
    pub = encode_public_key(key)
    client = AxisClient("http://127.0.0.1:8000")

    proof = client.build_proof(
        "dev_0123456789abcdef", {"max_power_kw": 2.5, "timestamp": "2026-08-21T12:00:00Z"}, key, nonce="n-2"
    )
    env = client.wrap_envelope(proof, signing_key=key)
    assert env.message_type == MessageType.PROOF.value
    assert client.verify_envelope(env, pub) is True


def test_http_error_raises():
    def transport(method, url, json=None):
        return httpx.Response(400, json={"detail": "bad request"})

    client = AxisClient("http://127.0.0.1:8000", transport=transport)
    try:
        client.submit_proof({})
        assert False, "expected HttpError"
    except HttpError as e:
        assert e.status_code == 400


def test_envelope_tamper_detected_by_sdk():
    key = _device_key()
    client = AxisClient("http://127.0.0.1:8000")
    proof = client.build_proof(
        "dev_0123456789abcdef", {"max_power_kw": 2.5, "timestamp": "2026-08-21T12:00:00Z"}, key, nonce="n-3"
    )
    env = client.wrap_envelope(proof, signing_key=key)
    env.message_payload["event_data"]["max_power_kw"] = 99.0
    assert client.verify_envelope(env, encode_public_key(key)) is False
