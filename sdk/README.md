# Axis Core SDK

A thin, dependency-light SDK for speaking the **Axis Protocol** with the
**Axis Core** reference service.

The SDK gives devices and integrators two layers:

| Layer | Module | What it gives you |
| :--- | :--- | :--- |
| **Trust Envelope** | `axis_core.wire` | Build, sign and verify the protocol wire format (`spec/protocol/wire-format.md`): identity, integrity, non-repudiation. |
| **REST client** | `axis_core.sdk` | Register devices, submit proofs, read attestations and device records through the reference HTTP API. |

## Design rules (the protocol constitution)

- **The private key never leaves the device** (ADR-0001). The SDK signs
  locally; only public keys and signatures travel over the wire.
- **The oracle verifies, never creates** (ADR-0003). The client submits
  proofs; the oracle's Policy Engine decides and the oracle signs the
  resulting attestation with its own key.
- **The Registry is the source of truth** (ADR-0002). Device state lives in
  the Device Registry, never in the client.

## Quick start

```python
import nacl.signing

from axis_core.sdk import AxisClient
from axis_core.signature_utils import encode_public_key

device_key = nacl.signing.SigningKey.generate()
client = AxisClient("http://127.0.0.1:8000")

# 1. Register the device (proof-of-possession — signed locally).
device_id = client.register(encode_public_key(device_key), signing_key=device_key)["device_id"]

# 2. Build a signed proof (payload carries the domain event data).
proof = client.build_proof(
    device_id,
    {"max_power_kw": 2.5, "timestamp": "2026-08-21T12:00:00Z"},
    device_key,
    nonce="n-000001",
)

# 3. Wrap it into a Trust Envelope and verify it locally.
envelope = client.wrap_envelope(proof, signing_key=device_key)
assert client.verify_envelope(envelope, encode_public_key(device_key))

# 4. Submit the proof — the oracle verifies and signs an attestation.
attestation = client.submit_proof(proof)
assert attestation["decision"]["allowed"] is True
```

## Transport injection

The default transport is `httpx.Client`. Tests (and constrained environments)
can inject any callable with the signature
`(method, url, json) -> httpx.Response`:

```python
import httpx

def fake_transport(method, url, json=None):
    return httpx.Response(200, json={"status": "ok"})

client = AxisClient("http://oracle.invalid", transport=fake_transport)
```

## Trust Envelope

The wire format (`spec/protocol/wire-format.md`) defines the **Trust
Envelope**: the cryptographic wrapper around every Axis message.

```
envelope_header (version, transport, correlation_id)
message_header  (message_type, version, domain, entity, issuer_id)
message_payload (Proof / Attestation / Claim)
signature       (Ed25519 over the ENTIRE envelope)
```

- Serialization is **deterministic** (canonical JSON) — the same logical
  message always yields the same bytes;
- the signature covers the **whole envelope** (header + payload), so nothing
  can be modified undetected;
- envelopes are **versioned** and self-describing.

See `tests/test_wire.py` for the exact guarantees.

## Reference

- Protocol: `Axis-protocol/spec/protocol/wire-format.md`
- API: `API.md`
- Policy Engine: `axis_core/policy` (ADR-0003)

