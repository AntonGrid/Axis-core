"""Trust Envelope container (``spec/protocol/wire-format.md`` §2).

The Trust Envelope wraps the message payload and provides identity, integrity
and non-repudiation. The cryptographic signature covers the **entire**
envelope (envelope header + message header + payload), so nothing can be
modified without detection.
"""
from __future__ import annotations

import base64
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import nacl.signing

from axis_core.signature_utils import canonical_json_bytes
from axis_core.wire.header import EnvelopeHeader, MessageHeader, MessageType, TransportId
from axis_core.wire.payloads import build_payload

#: Envelope format versions this implementation understands.
SUPPORTED_ENVELOPE_VERSIONS = (1,)


@dataclass
class TrustEnvelope:
    """A signed Axis message (wire-format §2.1).

    ``signature`` is Base64-encoded raw Ed25519 over the canonical JSON of the
    entire envelope **excluding** the ``signature`` field itself.
    """

    envelope_version: int = 1
    transport_id: str = TransportId.REST.value
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_header: Dict[str, Any] = field(default_factory=dict)
    message_payload: Dict[str, Any] = field(default_factory=dict)
    signature: str = ""  # base64 Ed25519 over the entire envelope

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrustEnvelope":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def signed_bytes(self) -> bytes:
        """Canonical bytes covered by the signature (envelope without ``signature``)."""
        body = {k: v for k, v in self.to_dict().items() if k != "signature"}
        return canonical_json_bytes(body)

    # ── Signing / verification ───────────────────────────────────────────────

    def sign(self, signing_key: nacl.signing.SigningKey) -> str:
        """Sign the entire envelope; returns (and stores) the Base64 signature."""
        signature = signing_key.sign(self.signed_bytes()).signature
        self.signature = base64.b64encode(signature).decode("ascii")
        return self.signature

    def verify(self, public_key_b64: str) -> bool:
        """Verify ``signature`` over the entire envelope for ``public_key_b64``."""
        if not self.signature:
            return False
        try:
            public_key = nacl.signing.VerifyKey(base64.b64decode(public_key_b64))
            sig = base64.b64decode(self.signature)
            public_key.verify(self.signed_bytes(), sig)
            return True
        except (ValueError, nacl.exceptions.BadSignatureError, nacl.exceptions.ValueError):
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def message_type(self) -> str:
        return self.message_header.get("message_type", "")

    @property
    def issuer_id(self) -> str:
        return self.message_header.get("issuer_id", "")


def _resolve_message_type(message_type: Any) -> str:
    if isinstance(message_type, MessageType):
        return message_type.value
    if isinstance(message_type, str):
        return message_type
    raise TypeError("message_type must be a MessageType or str")


def build_envelope(
    *,
    message_type: Any,
    payload: Dict[str, Any],
    issuer_id: str,
    signing_key: Optional[nacl.signing.SigningKey] = None,
    domain: str = "axis",
    entity_type: str = "device",
    entity_id: str = "",
    timestamp: Optional[str] = None,
    message_version: int = 1,
    envelope_version: int = 1,
    transport_id: str = TransportId.REST.value,
    correlation_id: Optional[str] = None,
    public_key_b64: Optional[str] = None,
) -> TrustEnvelope:
    """Build (and optionally sign) a Trust Envelope.

    ``payload`` is a plain dict matching the payload schema of
    ``message_type`` (see ``axis_core.wire.payloads``). When ``signing_key``
    is given the envelope is signed by it. ``issuer_id`` is the cryptographic
    identity of the issuer — pass the Base64 public key.
    """
    message_type_str = _resolve_message_type(message_type)

    header = MessageHeader(
        message_type=message_type_str,
        message_version=message_version,
        domain=domain,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=timestamp or "",
        issuer_id=issuer_id,
    )
    envelope_header = EnvelopeHeader(
        envelope_version=envelope_version,
        transport_id=transport_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
    )

    envelope = TrustEnvelope(
        envelope_version=envelope_header.envelope_version,
        transport_id=envelope_header.transport_id,
        correlation_id=envelope_header.correlation_id,
        message_header=header.to_dict(),
        message_payload=build_payload(message_type_str, payload),
    )

    if signing_key is not None:
        envelope.sign(signing_key)

    return envelope


def validate_envelope(envelope: TrustEnvelope) -> None:
    """Validate envelope structure per wire-format §8.

    Raises ``ValueError`` on the first violation:

    - ``envelope_version`` must be supported;
    - ``message_type`` must be known;
    - ``message_header`` must carry ``issuer_id``;
    - ``message_header`` must carry ``entity_id``.
    """
    if envelope.envelope_version not in SUPPORTED_ENVELOPE_VERSIONS:
        raise ValueError(
            f"unsupported envelope_version: {envelope.envelope_version} "
            f"(supported: {SUPPORTED_ENVELOPE_VERSIONS})"
        )

    header = envelope.message_header
    message_type = header.get("message_type")
    if message_type not in {t.value for t in MessageType}:
        raise ValueError(f"unknown message_type: {message_type!r}")

    if not header.get("issuer_id"):
        raise ValueError("message_header.issuer_id is required (wire-format §3)")

    if not header.get("entity_id"):
        raise ValueError("message_header.entity_id is required (wire-format §3)")


def verify_envelope(
    envelope: TrustEnvelope,
    public_key_b64: str,
    *,
    require_issuer_match: bool = True,
) -> bool:
    """Full wire-format §8 validation: structure, issuer binding, signature.

    When ``require_issuer_match`` is set, ``issuer_id`` must equal
    ``public_key_b64`` — the envelope is signed by the identity it claims.
    """
    try:
        validate_envelope(envelope)
    except ValueError:
        return False

    if require_issuer_match and envelope.issuer_id != public_key_b64:
        return False

    return envelope.verify(public_key_b64)
