"""Trust Envelope on the wire (wire-format §2/§8) — the `/oracle/attest` path.

The envelope codec itself is pinned by ``tests/test_wire.py``. These tests cover the
deployment question: **is the envelope actually authenticated when a message arrives?**
Until 2026-09-16 the codec was only exercised by the SDK, so nothing on the wire used
it; `POST /oracle/attest` now accepts an envelope and applies §8 in order —

1. structure (``validate_envelope``): supported ``envelope_version``, known
   ``message_type``, ``issuer_id``/``entity_id`` present → 400 otherwise;
2. authentication: unsigned → 401, signature over the whole envelope and the
   ``issuer_id == registered device key`` binding → 401, unknown device → 403;

and only then runs the device proof through the normal pipeline (the envelope proves
*this hop*, the inner signature proves *the device* — neither replaces the other).
"""
import copy

from fastapi.testclient import TestClient

from axis_core.main import app
from axis_core.sdk.client import AxisClient
from axis_core.signature_utils import encode_public_key

from tests.signature_helpers import (
    build_signed_proof,
    iso8601_z_offset_seconds,
    make_registered_device,
    now_iso8601_z,
)

client = TestClient(app)


def _sdk_no_network() -> AxisClient:
    """An SDK instance whose transport fails loudly (envelope building is local)."""

    def _transport(method, url, json=None):  # pragma: no cover - never called
        raise AssertionError(f"unexpected network call: {method} {url}")

    return AxisClient(base_url="http://testserver", transport=_transport)


def _sdk_over_testclient() -> AxisClient:
    """An SDK instance wired to the in-process app."""

    def _transport(method, url, json=None):
        return client.request(method, url, json=json)

    return AxisClient(base_url="http://testserver", transport=_transport)


def _envelope_for(device_id, key, max_power_kw=2.5):
    """A signed Trust Envelope, built by the SDK, carrying a valid device proof."""
    proof = build_signed_proof(
        key, device_id, "nonce-" + device_id[:8], now_iso8601_z(), max_power_kw
    )
    return proof, _sdk_no_network().wrap_envelope(proof, signing_key=key)


def test_envelope_wrapped_proof_is_accepted():
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)

    resp = client.post("/oracle/attest", json=envelope.to_dict())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["device_id"] == device_id
    assert body["decision"]["allowed"] is True
    assert body["decision"]["reason"] == "ok"
    assert body["attestation_id"]


def test_envelope_submitted_through_the_sdk():
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce-sdk", now_iso8601_z(), 2.5)

    body = _sdk_over_testclient().submit_proof(proof, envelope_signing_key=key)

    assert body["decision"]["allowed"] is True
    assert body["device_id"] == device_id


def test_plain_proof_body_is_still_accepted():
    """Backward compatibility: the envelope is an addition, not a replacement."""
    key, device_id = make_registered_device(client)
    proof = build_signed_proof(key, device_id, "nonce-plain", now_iso8601_z(), 2.5)

    resp = client.post("/oracle/attest", json=proof)

    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"]["allowed"] is True



def test_tampered_envelope_is_rejected():
    """§8: the signature covers the entire envelope, so any edit invalidates it."""
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)
    tampered = copy.deepcopy(envelope.to_dict())
    tampered["message_payload"]["event_data"]["max_power_kw"] = 99.0

    resp = client.post("/oracle/attest", json=tampered)

    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["reason"] == "envelope_signature_invalid"


def test_envelope_signed_by_another_identity_is_rejected():
    """The envelope must be signed by the identity it claims AND that identity must be
    the registered device — a valid signature by another (even registered) key is not
    enough."""
    other_key, _ = make_registered_device(client)
    key, device_id = make_registered_device(client)
    proof, _ = _envelope_for(device_id, key)
    # Same device_id/entity, but signed and claimed by a different identity.
    forged = _sdk_no_network().wrap_envelope(proof, signing_key=other_key)

    resp = client.post("/oracle/attest", json=forged.to_dict())

    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["reason"] == "envelope_signature_invalid"


def test_unsigned_envelope_is_rejected():
    key, device_id = make_registered_device(client)
    proof, _ = _envelope_for(device_id, key)
    unsigned = _sdk_no_network().wrap_envelope(
        proof, public_key_b64=encode_public_key(key)
    )

    resp = client.post("/oracle/attest", json=unsigned.to_dict())

    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["reason"] == "envelope_unsigned"


def test_unknown_device_envelope_is_403():
    """No key on file → the envelope cannot be authenticated at all."""
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)
    body = envelope.to_dict()
    body["message_payload"]["device_id"] = "device_that_is_not_registered"

    resp = client.post("/oracle/attest", json=body)

    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["reason"] == "device_not_registered"


def test_unsupported_envelope_version_is_rejected():
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)
    body = envelope.to_dict()
    body["envelope_version"] = 99

    resp = client.post("/oracle/attest", json=body)

    assert resp.status_code == 400, resp.text
    assert "envelope_version" in str(resp.json()["detail"])


def test_unknown_message_type_is_rejected():
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)
    body = envelope.to_dict()
    body["message_header"]["message_type"] = "telemetry"

    resp = client.post("/oracle/attest", json=body)

    assert resp.status_code == 400, resp.text
    assert "message_type" in str(resp.json()["detail"])


def test_header_and_payload_timestamp_must_agree():
    """A hand-built envelope must not be able to claim two different times. The check
    runs after authentication, so the envelope is re-signed to reach it."""
    key, device_id = make_registered_device(client)
    _, envelope = _envelope_for(device_id, key)
    envelope.message_header["timestamp"] = iso8601_z_offset_seconds(-3600)
    envelope.sign(key)

    resp = client.post("/oracle/attest", json=envelope.to_dict())

    assert resp.status_code == 400, resp.text
    assert "disagrees" in str(resp.json()["detail"])
