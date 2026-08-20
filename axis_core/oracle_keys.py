"""Oracle Ed25519 signing key management (ADR-0001).

The oracle verifies device proofs and then certifies the outcome of that
verification by signing the attestation with its own Ed25519 key. The oracle
key is unrelated to any device key: device private keys never leave the device.
"""
import base64
import os
from typing import Any, Dict

import nacl.signing

from axis_core.signature_utils import canonical_attestation_message, verify_ed25519_signature


class OracleKeyNotConfigured(Exception):
    """Raised when the oracle signing key is required but not configured."""


def _signing_key_from_b64(secret_key_b64: str) -> nacl.signing.SigningKey:
    seed = base64.b64decode(secret_key_b64, validate=True)
    if len(seed) != 32:
        raise ValueError("oracle secret key must decode to exactly 32 bytes")
    return nacl.signing.SigningKey(seed)


def load_oracle_secret_key() -> nacl.signing.SigningKey:
    """Load the oracle signing key from ``ORACLE_SECRET_KEY`` (Base64 seed)."""
    secret_key_b64 = os.environ.get("ORACLE_SECRET_KEY", "").strip()
    if not secret_key_b64:
        raise OracleKeyNotConfigured(
            "oracle key not configured: set ORACLE_SECRET_KEY "
            "(Base64-encoded 32-byte Ed25519 seed)"
        )
    try:
        return _signing_key_from_b64(secret_key_b64)
    except ValueError as e:
        raise OracleKeyNotConfigured(
            "ORACLE_SECRET_KEY is not a valid Base64-encoded 32-byte Ed25519 seed"
        ) from e


def sign_attestation(attestation: Dict[str, Any], secret_key_b64: str) -> str:
    """Sign the canonical attestation (without the ``oracle_signature`` field)."""
    signing_key = _signing_key_from_b64(secret_key_b64)
    message = canonical_attestation_message(attestation)
    signature = signing_key.sign(message).signature
    return base64.b64encode(signature).decode("ascii")


def verify_oracle_signature(attestation: Dict[str, Any], public_key_b64: str) -> bool:
    """Verify the ``oracle_signature`` of an attestation against a public key."""
    return verify_ed25519_signature(
        public_key_b64,
        canonical_attestation_message(attestation),
        attestation.get("oracle_signature", ""),
    )


def encode_oracle_public_key(secret_key_b64: str) -> str:
    """Return the Base64 public key that corresponds to ``secret_key_b64``."""
    signing_key = _signing_key_from_b64(secret_key_b64)
    return base64.b64encode(bytes(signing_key.verify_key)).decode("ascii")


def encode_secret_key(signing_key: nacl.signing.SigningKey) -> str:
    """Base64-encode an Ed25519 signing key seed (reference tooling / tests)."""
    return base64.b64encode(bytes(signing_key)).decode("ascii")
