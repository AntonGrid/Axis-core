"""Shared helpers for tests that exercise real Ed25519 device signatures."""
from typing import Any, Dict, Optional

from nacl.signing import SigningKey

from axis_core.signature_utils import encode_public_key, generate_device_key, sign_proof


def register_device(client, public_key_b64: str, manifest_ref: Optional[str] = None) -> str:
    """Register a device and return its deterministic ``device_id``."""
    body = {"public_key": public_key_b64}
    if manifest_ref is not None:
        body["manifest_ref"] = manifest_ref
    resp = client.post("/provisioning/register", json=body)
    assert resp.status_code == 200, f"registration failed: {resp.text}"
    return resp.json()["device_id"]


def build_signed_proof(
    key: SigningKey,
    device_id: str,
    nonce: str,
    timestamp: str,
    max_power_kw: float,
    algo: str = "ed25519",
) -> Dict[str, Any]:
    """Build a proof body signed by ``key`` over the canonical message."""
    body: Dict[str, Any] = {
        "device_id": device_id,
        "nonce": nonce,
        "timestamp": timestamp,
        "algo": algo,
        "payload": {"max_power_kw": max_power_kw},
    }
    body["signature"] = sign_proof(key, body)
    return body


def make_registered_device(client) -> tuple:
    """Create an Ed25519 keypair and register the device; returns (key, device_id)."""
    key = generate_device_key()
    public_key_b64 = encode_public_key(key)
    device_id = register_device(client, public_key_b64)
    return key, device_id
