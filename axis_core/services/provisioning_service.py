import hashlib
from dataclasses import dataclass
from typing import Dict

from axis_core.config import mock_mode_enabled
from axis_core.signature_utils import (
    canonical_registration_message,
    is_valid_public_key_b64,
    verify_ed25519_signature,
)


@dataclass
class RegisteredDevice:
    device_id: str
    public_key: str
    manifest_ref: str
    bootstrap_policy: Dict


_DB: Dict[str, RegisteredDevice] = {}


def _generate_device_id(public_key: str) -> str:
    return "dev_" + hashlib.sha256(public_key.encode()).hexdigest()[:16]


def register_device(req) -> Dict:
    public_key = req.public_key
    if not public_key:
        raise ValueError("public_key is required")
    if not is_valid_public_key_b64(public_key):
        raise ValueError("public_key must be a Base64-encoded 32-byte Ed25519 key")

    # Proof of possession (ADR-0001): the device must prove it holds the
    # private key that corresponds to the public key it registers. In dev mode
    # (AXIS_ALLOW_MOCK=1) the signature may be omitted for tooling/tests.
    signature = req.signature
    nonce = req.nonce
    if not mock_mode_enabled():
        if not signature or not nonce:
            raise ValueError("signature and nonce are required (proof of possession)")
        message = canonical_registration_message(public_key, nonce)
        if not verify_ed25519_signature(public_key, message, signature):
            raise ValueError("invalid signature: proof of device key ownership required")

    device_id = _generate_device_id(public_key)
    manifest_ref = req.manifest_ref or "manifest:v0-placeholder"

    bootstrap_policy = {
        "allowed": True,
        "max_power_kw": 3.5,
    }

    _DB[device_id] = RegisteredDevice(
        device_id=device_id,
        public_key=public_key,
        manifest_ref=manifest_ref,
        bootstrap_policy=bootstrap_policy,
    )

    return {
        "device_id": device_id,
        "manifest_ref": manifest_ref,
        "bootstrap_policy": bootstrap_policy,
    }

