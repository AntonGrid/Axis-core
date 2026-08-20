"""Shared helpers for tests that exercise real Ed25519 device signatures."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from nacl.signing import SigningKey

from axis_core.signature_utils import (
    encode_public_key,
    generate_device_key,
    sign_proof,
    sign_registration,
)


def now_iso8601_z() -> str:
    """Return the current UTC time as an ISO 8601 timestamp with a 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iso8601_z_offset_seconds(offset_seconds: int) -> str:
    """Return an ISO 8601 'Z' timestamp offset from now by ``offset_seconds``."""
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def register_device(
    client,
    public_key_b64: str,
    signing_key: Optional[SigningKey] = None,
    manifest_ref: Optional[str] = None,
) -> str:
    """Register a device (with proof-of-possession) and return its ``device_id``."""
    body: Dict[str, Any] = {"public_key": public_key_b64}
    if signing_key is not None:
        nonce = "reg-" + public_key_b64[:16]
        body["nonce"] = nonce
        body["signature"] = sign_registration(signing_key, public_key_b64, nonce)
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
    device_id = register_device(client, public_key_b64, signing_key=key)
    return key, device_id

