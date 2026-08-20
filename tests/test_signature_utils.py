"""Unit tests for canonical JSON serialization and strict key/signature decoding."""
import base64

import nacl.signing

from axis_core.signature_utils import (
    canonical_json_bytes,
    canonical_proof_message,
    is_valid_public_key_b64,
    verify_ed25519_signature,
)


def test_canonical_json_integral_float_equals_int():
    assert canonical_json_bytes({"x": 2}) == canonical_json_bytes({"x": 2.0})
    assert canonical_json_bytes({"x": 2}) == b'{"x":2}'


def test_canonical_json_nested_and_sorted_keys():
    assert canonical_json_bytes({"b": 1, "a": {"d": 2, "c": 3}}) == b'{"a":{"c":3,"d":2},"b":1}'


def test_canonical_json_non_integral_float_preserved():
    assert canonical_json_bytes({"x": 2.5}) == b'{"x":2.5}'


def test_canonical_proof_message_normalizes_numbers():
    body_int = {
        "device_id": "dev_x",
        "nonce": "n",
        "timestamp": "t",
        "algo": "ed25519",
        "payload": {"max_power_kw": 2},
    }
    body_float = {**body_int, "payload": {"max_power_kw": 2.0}}
    assert canonical_proof_message(body_int) == canonical_proof_message(body_float)


def test_verify_ed25519_signature_rejects_wrong_lengths():
    key = nacl.signing.SigningKey.generate()
    pk = base64.b64encode(bytes(key.verify_key)).decode("ascii")

    # Wrong signature length (not 64 bytes).
    assert verify_ed25519_signature(pk, b"hello", base64.b64encode(b"short").decode()) is False
    # Wrong public key length (not 32 bytes).
    assert (
        verify_ed25519_signature(base64.b64encode(b"not32bytes").decode(), b"hello", base64.b64encode(b"x" * 64).decode())
        is False
    )


def test_is_valid_public_key_b64():
    key = nacl.signing.SigningKey.generate()
    pk = base64.b64encode(bytes(key.verify_key)).decode("ascii")
    assert is_valid_public_key_b64(pk) is True
    assert is_valid_public_key_b64("not base64!!") is False
    assert is_valid_public_key_b64(base64.b64encode(b"short").decode()) is False
