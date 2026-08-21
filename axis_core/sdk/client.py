"""AxisClient — the Axis Core SDK client.

Protocol reference: ``spec/protocol/wire-format.md`` (Axis-protocol repo),
API reference: ``API.md`` (this repository).

The client has two layers:

1. **Envelope layer** — builds and verifies Trust Envelopes
   (``axis_core.wire``): identity, integrity, non-repudiation;
2. **REST layer** — the reference HTTP API of the Axis Core service
   (``/provisioning/register``, ``/oracle/attest``, ``/registry/devices/...``).

Design notes:

- The private key **never leaves the device** (ADR-0001): the SDK signs
  locally and only sends public keys and signatures over the wire;
- The oracle **verifies, never creates** (ADR-0003): the client only submits
  proofs; the attestation is produced and signed by the oracle.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import httpx
import nacl.signing

from axis_core.signature_utils import (
    canonical_proof_message,
    encode_public_key,
    sign_proof,
    sign_registration,
)
from axis_core.wire.envelope import TrustEnvelope, build_envelope, verify_envelope
from axis_core.wire.header import MessageType

#: Any callable ``(method, url, json) -> httpx.Response``.
Transport = Callable[..., httpx.Response]


def _default_transport(base_url: str) -> Transport:
    client = httpx.Client(base_url=base_url, timeout=30.0)

    def request(method: str, url: str, json: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return client.request(method, url, json=json)

    return request


class HttpError(Exception):
    """Raised for non-2xx responses from the Axis Core service."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class AxisClient:
    """High-level Axis Core client.

    ``base_url`` — the API root (e.g. ``http://127.0.0.1:8000``).
    ``transport`` — optional injectable transport for tests
    (default: ``httpx.Client``).
    """

    def __init__(
        self,
        base_url: str,
        transport: Optional[Transport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport or _default_transport(self.base_url)

    # ── Low-level HTTP ───────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        resp = self._transport(method, f"{self.base_url}{path}", json=json)
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            raise HttpError(resp.status_code, detail)
        return resp


    # ── REST API ─────────────────────────────────────────────────────────────

    def register(
        self,
        public_key_b64: str,
        signing_key: Optional[nacl.signing.SigningKey] = None,
        manifest_ref: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a device (proof-of-possession, ADR-0001/0002).

        When ``signing_key`` is given, the proof-of-possession signature is
        produced locally (the key never leaves the device).
        """
        body: Dict[str, Any] = {"public_key": public_key_b64}
        if signing_key is not None:
            reg_nonce = nonce or ("reg-" + public_key_b64[:16])
            body["nonce"] = reg_nonce
            body["signature"] = sign_registration(signing_key, public_key_b64, reg_nonce)
        if manifest_ref is not None:
            body["manifest_ref"] = manifest_ref
        resp = self._request("POST", "/provisioning/register", json=body)
        return resp.json()

    def submit_proof(self, proof: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a signed proof to the oracle attestation endpoint."""
        resp = self._request("POST", "/oracle/attest", json=proof)
        return resp.json()

    def attestations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List attestations (paginated)."""
        resp = self._request("GET", f"/oracle/attestations?limit={limit}&offset={offset}")
        return resp.json()

    def device_status(self, device_id: str) -> Dict[str, Any]:
        """Read the device record from the Registry (source of truth, ADR-0002)."""
        resp = self._request("GET", f"/registry/devices/{device_id}")
        return resp.json()

    # ── Trust Envelope layer ─────────────────────────────────────────────────

    def build_proof(
        self,
        device_id: str,
        event_data: Dict[str, Any],
        signing_key: nacl.signing.SigningKey,
        nonce: str,
    ) -> Dict[str, Any]:
        """Build and sign a proof body (canonical message per signature_utils)."""
        body: Dict[str, Any] = {
            "device_id": device_id,
            "nonce": nonce,
            "timestamp": event_data.get("timestamp", ""),
            "algo": "ed25519",
            "payload": event_data,
        }
        body["signature"] = sign_proof(signing_key, body)
        return body

    def wrap_envelope(
        self,
        proof: Dict[str, Any],
        signing_key: Optional[nacl.signing.SigningKey] = None,
        public_key_b64: Optional[str] = None,
    ) -> TrustEnvelope:
        """Wrap a proof into a signed Trust Envelope (wire-format §2).

        ``issuer_id`` is the device's public key (Base64). When ``signing_key``
        is omitted, the envelope is left unsigned for the caller to sign.
        """
        issuer = public_key_b64 or (
            encode_public_key(signing_key) if signing_key else ""
        )
        if not issuer:
            raise ValueError("either signing_key or public_key_b64 is required")
        return build_envelope(
            message_type=MessageType.PROOF,
            payload={
                "device_id": proof["device_id"],
                "event_data": proof.get("payload", {}),
                "timestamp": _ts_to_epoch(proof.get("timestamp", "")),
                "nonce": proof.get("nonce", ""),
                "signature": proof.get("signature", ""),
            },
            issuer_id=issuer,
            signing_key=signing_key,
            entity_type="device",
            entity_id=proof["device_id"],
            timestamp=proof.get("timestamp", ""),
        )

    @staticmethod
    def verify_envelope(envelope: TrustEnvelope, public_key_b64: str) -> bool:
        """Verify a Trust Envelope: structure, issuer binding, signature."""
        return verify_envelope(envelope, public_key_b64)


def _ts_to_epoch(ts: str) -> int:
    from datetime import datetime, timezone

    if not ts:
        return 0
    iso = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
