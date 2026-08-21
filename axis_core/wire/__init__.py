"""Trust Envelope wire format (Axis Protocol ``spec/protocol/wire-format.md``).

The Trust Envelope is the carrier of trust between physical devices and
digital systems: it wraps a message payload and provides identity, integrity
and non-repudiation. Every envelope is:

- **deterministic** — the same logical message always serializes to the same
  byte sequence (canonical JSON);
- **versioned** — envelopes are self-describing and can evolve;
- **signed as a whole** — the cryptographic signature covers the entire
  envelope (header + payload), so nothing can be modified undetected.

Components:

- ``header`` — the envelope and message headers (``envelope_version``,
  ``transport_id``, ``correlation_id``, ``message_type``, ``domain``,
  ``entity_type``, ``entity_id``, ``timestamp``, ``issuer_id``);
- ``payloads`` — the canonical payloads (Proof, Attestation, Claim);
- ``envelope`` — the ``TrustEnvelope`` container: build, serialize, sign,
  validate and verify.
"""

from axis_core.wire.envelope import (
    TrustEnvelope,
    build_envelope,
    validate_envelope,
    verify_envelope,
)
from axis_core.wire.header import MessageHeader, MessageType, TransportId
from axis_core.wire.payloads import (
    AttestationPayload,
    ClaimPayload,
    ProofPayload,
    build_payload,
)

__all__ = [
    "AttestationPayload",
    "ClaimPayload",
    "MessageHeader",
    "MessageType",
    "ProofPayload",
    "TransportId",
    "TrustEnvelope",
    "build_envelope",
    "build_payload",
    "validate_envelope",
    "verify_envelope",
]
