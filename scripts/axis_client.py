"""Shared minimal HTTP client and Ed25519 signing helpers for Axis Core demos.

All demo scripts talk to the same backend API, so the client lives here instead
of being duplicated inline. It is a *reference* client: it demonstrates the
provisioning → attestation flow, including real Ed25519 device signatures.
"""
import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from nacl.signing import SigningKey


@dataclass
class AxisClient:
    """Minimal HTTP client for the Axis Core backend."""

    base_url: str = "http://localhost:8000"

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def health(self) -> Dict[str, Any]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def register_device(self, public_key: str, manifest_ref: Optional[str] = None) -> Dict[str, Any]:
        body = {"public_key": public_key}
        if manifest_ref is not None:
            body["manifest_ref"] = manifest_ref
        resp = self._client.post("/provisioning/register", json=body)
        resp.raise_for_status()
        return resp.json()

    def oracle_attest_request(
        self,
        device_id: str,
        nonce: str,
        max_power_kw: float,
        algo: str = "ed25519",
        signing_key: Optional[SigningKey] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        if timestamp is None:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            timestamp = now.isoformat().replace("+00:00", "Z")

        payload: Dict[str, Any] = {
            "device_id": device_id,
            "nonce": nonce,
            "timestamp": timestamp,
            "algo": algo,
            "payload": {"max_power_kw": max_power_kw},
        }
        payload["signature"] = sign_proof_body(payload, algo, signing_key)

        resp = self._client.post("/oracle/attest", json=payload)
        resp.raise_for_status()
        return resp.json()


def sign_proof_body(
    payload: Dict[str, Any],
    algo: str,
    signing_key: Optional[SigningKey],
) -> str:
    """Sign a proof body or fall back to the mock placeholder.

    For ``algo="ed25519"`` the message is the canonical JSON serialization of
    (device_id, nonce, timestamp, algo, payload) — see
    ``axis_core.signature_utils.canonical_proof_message``.
    """
    if algo == "ed25519" and signing_key is not None:
        message = json.dumps(
            {k: payload[k] for k in ("device_id", "nonce", "timestamp", "algo", "payload")},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        signature = signing_key.sign(message).signature
        return base64.b64encode(signature).decode("ascii")
    return "deadbeef" * 8


def generate_device_key() -> SigningKey:
    """Generate a fresh Ed25519 device key."""
    return SigningKey.generate()


def encode_public_key(key: SigningKey) -> str:
    """Base64-encode the device public key for registration."""
    return base64.b64encode(bytes(key.verify_key)).decode("ascii")
