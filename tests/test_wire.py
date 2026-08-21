"""Trust Envelope tests (Axis Protocol wire format).

The normative spec lives in ``Axis-protocol/spec/protocol/wire-format.md``.
These tests pin the implementation guarantees:

- deterministic serialization (same message → same bytes);
- the signature covers the ENTIRE envelope (header + payload);
- tampering with any field invalidates the signature;
- structural validation per wire-format §8.
"""
import base64

import nacl.signing
import pytest

from axis_core.signature_utils import encode_public_key
from axis_core.wire import (
    MessageHeader,
    MessageType,
    TrustEnvelope,
    build_envelope,
    validate_envelope,
    verify_envelope,
)
from axis_core.wire.envelope import SUPPORTED_ENVELOPE_VERSIONS


def _keypair():
    key = nacl.signing.SigningKey.generate()
    return key, encode_public_key(key)


def _sample_payload() -> dict:
    return {
        "device_id": "dev_0123456789abcdef",
        "event_data": {"energy_wh": 1500},
        "timestamp": 1_700_000_000,
        "nonce": "n-000001",
        "signature": base64.b64encode(b"\x01" * 64).decode("ascii"),
    }


def test_build_signed_envelope_verifies():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
    )
    assert env.message_type == "proof"
    assert env.signature
    assert verify_envelope(env, pub) is True


def test_signature_covers_entire_envelope():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
    )

    # Tamper with the PAYLOAD.
    tampered = TrustEnvelope.from_dict(env.to_dict())
    tampered.message_payload["event_data"]["energy_wh"] = 9_999_999
    assert tampered.verify(pub) is False
    assert verify_envelope(tampered, pub) is False

    # Tamper with the MESSAGE HEADER.
    tampered2 = TrustEnvelope.from_dict(env.to_dict())
    tampered2.message_header["entity_id"] = "dev_other"
    assert tampered2.verify(pub) is False

    # Tamper with the ENVELOPE HEADER (correlation_id).
    tampered3 = TrustEnvelope.from_dict(env.to_dict())
    tampered3.correlation_id = "different"
    assert tampered3.verify(pub) is False


def test_signature_from_wrong_key_rejected():
    key, _ = _keypair()
    other_key, other_pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=other_pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
    )
    assert env.verify(other_pub) is False
    assert verify_envelope(env, other_pub) is False


def test_issuer_binding_required():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
    )
    # issuer_id does not match the public key that verifies the signature.
    assert verify_envelope(env, pub) is True
    env.message_header["issuer_id"] = "someone_else"
    assert verify_envelope(env, pub) is False


def test_deterministic_serialization():
    key, pub = _keypair()
    env1 = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
        correlation_id="fixed-correlation",
    )
    env2 = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
        correlation_id="fixed-correlation",
    )
    assert env1.signed_bytes() == env2.signed_bytes()
    assert env1.to_dict() == env2.to_dict()


def test_validation_rejects_unknown_message_type():
    key, pub = _keypair()
    # build_envelope rejects unknown types at build time (build_payload); to
    # exercise the validator we craft the envelope directly.
    env = TrustEnvelope(
        envelope_version=1,
        transport_id="rest",
        correlation_id="c",
        message_header={
            "message_type": "telemetry",
            "message_version": 1,
            "domain": "axis",
            "entity_type": "device",
            "entity_id": "dev_0123456789abcdef",
            "timestamp": "2026-08-21T12:00:00Z",
            "issuer_id": pub,
        },
        message_payload={"device_id": "dev_0123456789abcdef"},
    )
    with pytest.raises(ValueError, match="unknown message_type"):
        validate_envelope(env)


def test_validation_rejects_missing_issuer():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
    )
    env.message_header["issuer_id"] = ""
    with pytest.raises(ValueError, match="issuer_id"):
        validate_envelope(env)


def test_validation_rejects_unsupported_version():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.PROOF,
        payload=_sample_payload(),
        issuer_id=pub,
        signing_key=key,
        entity_id="dev_0123456789abcdef",
        envelope_version=99,
    )
    assert 99 not in SUPPORTED_ENVELOPE_VERSIONS
    with pytest.raises(ValueError, match="unsupported envelope_version"):
        validate_envelope(env)


def test_message_header_roundtrip():
    header = MessageHeader(
        message_type="proof",
        message_version=1,
        domain="axis",
        entity_type="device",
        entity_id="dev_1",
        timestamp="2026-08-21T12:00:00Z",
        issuer_id="issuer",
    )
    restored = MessageHeader.from_dict(header.to_dict())
    assert restored == header


def test_attestation_envelope_roundtrip():
    key, pub = _keypair()
    env = build_envelope(
        message_type=MessageType.ATTESTATION,
        payload={
            "proof_id": "proof_1",
            "decision": "valid",
            "oracle_id": "oracle_main_1",
        },
        issuer_id=pub,
        signing_key=key,
        entity_type="oracle",
        entity_id="oracle_main_1",
    )
    assert env.message_type == "attestation"
    assert verify_envelope(env, pub) is True
