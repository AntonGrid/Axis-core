"""Envelope and message headers (``spec/protocol/wire-format.md`` §2–§3).

The envelope header carries transport-level metadata; the message header
provides the metadata required to interpret the payload and establish trust
context. ``issuer_id`` binds the message to a specific cryptographic identity
and is **critical** for trust.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_iso8601_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class MessageType(str, enum.Enum):
    """High-level message classification (wire-format §4).

    Values mirror the specification's numeric codes but are carried as stable
    strings in the JSON codec so the envelope stays self-describing.
    """

    PROOF = "proof"  # 0x01 — cryptographic proof of a physical event
    ATTESTATION = "attestation"  # 0x02 — signed verification of a Proof
    CLAIM = "claim"  # 0x03 — digital statement backed by an Attestation

    @property
    def code(self) -> int:
        return {"proof": 0x01, "attestation": 0x02, "claim": 0x03}[self.value]


class TransportId(str, enum.Enum):
    """Known transport/channel identifiers (wire-format §2.2)."""

    REST = "rest"  # JSON over HTTP(S)
    WS = "ws"  # JSON over WebSocket
    SOLANA = "solana"  # carried inside Solana transaction instructions
    MQTT = "mqtt"  # MQTT QoS topic
    FILE = "file"  # file-based ingestion (bulk import)


@dataclass(frozen=True)
class EnvelopeHeader:
    """Transport-level envelope header (wire-format §2.2)."""

    envelope_version: int = 1
    transport_id: str = TransportId.REST.value
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvelopeHeader":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass(frozen=True)
class MessageHeader:
    """Message header (wire-format §3).

    ``issuer_id`` is the cryptographic identity of the issuer — it must be the
    identity that signs the envelope.
    """

    message_type: str
    message_version: int = 1
    domain: str = "axis"
    entity_type: str = "device"
    entity_id: str = ""
    timestamp: str = field(default_factory=_now_iso8601_z)
    issuer_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageHeader":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def with_entity(
        self,
        *,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        issuer_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> "MessageHeader":
        """Return a copy with entity/issuer fields overridden."""
        return MessageHeader(
            message_type=self.message_type,
            message_version=self.message_version,
            domain=domain or self.domain,
            entity_type=entity_type or self.entity_type,
            entity_id=entity_id if entity_id is not None else self.entity_id,
            timestamp=self.timestamp,
            issuer_id=issuer_id if issuer_id is not None else self.issuer_id,
        )
