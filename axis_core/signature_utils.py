"""Ed25519 signature verification for Axis Core.

The oracle *verifies* device proofs; it never creates them and never holds
private keys (ADR-0001). This module provides:

- the **canonical message** that a device signs (deterministic, documented in
  ``docs/conformance.md``);
- the **Ed25519 verification** entry point (PyNaCl).

Canonical message format (v1)
-----------------------------

The signed message is the UTF-8 encoding of the canonical JSON serialization of
the proof fields *excluding* ``signature``:

    {"algo":..., "device_id":..., "nonce":..., "payload":{...}, "timestamp":...}

Canonical JSON means: keys sorted lexicographically, no whitespace, ``,`` and
``:`` separators (the same canonical form used by the reference scripts).
``payload`` is an arbitrary JSON object; device implementations MUST use a
language-agnostic canonical JSON serializer so the exact byte string matches.

Key and signature encoding
--------------------------

Both the device public key (registered in the Device Registry) and the proof
signature are **Base64-encoded** raw Ed25519 bytes (32-byte public key,
64-byte signature) — the same encoding used by ENRG reference tooling.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict

import nacl.exceptions
import nacl.signing

#: Proof fields covered by the device signature (in canonical order for docs).
SIGNED_PROOF_FIELDS = ("device_id", "nonce", "timestamp", "algo", "payload")

#: Algorithms the oracle can verify. ``mock`` is a documented dev-only mode.
SUPPORTED_ALGOS = ("ed25519", "mock")


def _normalize_numbers(value: Any) -> Any:
    """Make JSON numbers canonical across implementations.

    A float that is exactly an integer (e.g. ``2.0``) is serialized as an
    integer (``2``) so that ``2`` and ``2.0`` produce identical bytes. All
    other values are returned unchanged (nested objects/arrays are recursed).
    """
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, dict):
        return {k: _normalize_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_numbers(v) for v in value]
    return value


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON serialization used for all signed messages.

    Keys are sorted lexicographically, whitespace is removed, and floats that
    equal an integer are normalized to integers (see ``_normalize_numbers``).
    """
    return json.dumps(
        _normalize_numbers(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_proof_message(proof: Dict[str, Any]) -> bytes:
    """Return the canonical bytes a device must sign for a given proof body.

    The ``signature`` field (if present) is excluded from the signed message.
    """
    body = {k: proof[k] for k in SIGNED_PROOF_FIELDS if k in proof}
    return canonical_json_bytes(body)


def canonical_attestation_message(attestation: Dict[str, Any]) -> bytes:
    """Return the canonical bytes the oracle signs for an attestation.

    The ``oracle_signature`` field is excluded from the signed message.
    """
    body = {k: v for k, v in attestation.items() if k != "oracle_signature"}
    return canonical_json_bytes(body)


def canonical_registration_message(public_key_b64: str, nonce: str) -> bytes:
    """Return the canonical bytes a device signs to prove key ownership."""
    return canonical_json_bytes({"nonce": nonce, "public_key": public_key_b64})


def verify_ed25519_signature(
    public_key_b64: str,
    message: bytes,
    signature_b64: str,
) -> bool:
    """Verify a Base64-encoded Ed25519 signature over ``message``.

    Returns ``True`` only if the signature is valid for ``public_key_b64``.
    Invalid Base64, wrong-length keys/signatures, or bad signatures return
    ``False`` (never raise).
    """
    try:
        public_key_bytes = base64.b64decode(public_key_b64, validate=True)
        signature_bytes = base64.b64decode(signature_b64, validate=True)
    except ValueError:
        return False

    if len(public_key_bytes) != 32 or len(signature_bytes) != 64:
        return False

    try:
        public_key = nacl.signing.VerifyKey(public_key_bytes)
        public_key.verify(message, signature_bytes)
        return True
    except (ValueError, nacl.exceptions.BadSignatureError):
        return False


def sign_proof(secret_key: nacl.signing.SigningKey, proof: Dict[str, Any]) -> str:
    """Sign a proof body with a device key; returns Base64 signature.

    Intended for tests and reference tooling — never used on the oracle path.
    """
    message = canonical_proof_message(proof)
    signature = secret_key.sign(message).signature
    return base64.b64encode(signature).decode("ascii")


def encode_public_key(secret_key: nacl.signing.SigningKey) -> str:
    """Base64-encode the public key of a device signing key (reference tooling)."""
    return base64.b64encode(bytes(secret_key.verify_key)).decode("ascii")


def sign_registration(
    secret_key: nacl.signing.SigningKey,
    public_key_b64: str,
    nonce: str,
) -> str:
    """Sign the proof-of-possession message for device registration."""
    message = canonical_registration_message(public_key_b64, nonce)
    signature = secret_key.sign(message).signature
    return base64.b64encode(signature).decode("ascii")


def is_valid_public_key_b64(public_key_b64: str) -> bool:
    """Return True if ``public_key_b64`` is a strict Base64 32-byte key."""
    try:
        raw = base64.b64decode(public_key_b64, validate=True)
    except ValueError:
        return False
    return len(raw) == 32


def generate_device_key() -> nacl.signing.SigningKey:
    """Generate a fresh Ed25519 device key (reference tooling / tests)."""
    return nacl.signing.SigningKey.generate()
