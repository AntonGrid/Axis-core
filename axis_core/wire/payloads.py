"""Canonical message payloads (``spec/protocol/wire-format.md`` §5).

A Proof is the atomic unit of trust from the physical world; an Attestation is
a signed verification of a Proof by a trusted entity; a Claim is a digital
statement backed by an Attestation.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from axis_core.signature_utils import canonical_json_bytes


def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _now_epoch_field() -> int:
    """Dataclass-friendly default that evaluates at call time."""
    return _now_epoch()


@dataclass
class ProofPayload:
    """Wire-format ``ProofPayload`` (§5.1)."""

    device_id: str
    event_data: Dict[str, Any]
    timestamp: int
    nonce: str
    signature: str = ""  # base64 Ed25519, signed by the device private key

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProofPayload":
        return cls(**data)

    def signed_bytes(self) -> bytes:
        """Deterministic bytes covered by ``signature`` (payload without it)."""
        body = {k: v for k, v in self.to_dict().items() if k != "signature"}
        return canonical_json_bytes(body)


@dataclass
class AttestationPayload:
    """Wire-format ``AttestationPayload`` (§5.2)."""

    proof_id: str
    decision: str  # "valid" / "invalid"
    oracle_id: str
    timestamp: int = _now_epoch_field()
    signature: str = ""  # base64 Ed25519, signed by the oracle private key

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttestationPayload":
        return cls(**data)

    def signed_bytes(self) -> bytes:
        body = {k: v for k, v in self.to_dict().items() if k != "signature"}
        return canonical_json_bytes(body)


@dataclass
class ClaimPayload:
    """Wire-format ``ClaimPayload`` (§5.3)."""

    attestation_id: str
    statement: Dict[str, Any]
    timestamp: int = _now_epoch_field()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimPayload":
        return cls(**data)


def build_payload(message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a payload dict for ``message_type`` from a plain dict."""
    if message_type == "proof":
        return ProofPayload.from_dict(data).to_dict()
    if message_type == "attestation":
        return AttestationPayload.from_dict(data).to_dict()
    if message_type == "claim":
        return ClaimPayload.from_dict(data).to_dict()
    raise ValueError(f"unknown message_type: {message_type!r}")

