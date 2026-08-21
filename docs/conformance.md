# Axis Core — Conformance

This document records how **Axis Core** (the reference implementation) relates to
the **Axis Protocol** specification, what is verified automatically, and which
known deviations exist. The normative protocol specification lives in the
Axis-protocol repository (`spec/` and `adr/`).

---

## 1. What is verified automatically

The conformance tests live in `tests/test_conformance.py` and are part of the
standard test run (`pytest -q`). They verify:

1. **OpenAPI ↔ routes.** The committed `openapi.yaml` documents exactly the
   endpoints the FastAPI application exposes (`app.openapi()`), no more and no
   less: `/health`, `/provisioning/register`, `/provisioning/attest`,
   `/registry/devices/{device_id}`, `/oracle/attest`, `/oracle/attestations`,
   `/oracle/attestations/{attestation_id}`, `/oracle/requests`,
   `/oracle/requests/{request_id}`.

2. **Canonical ↔ runtime schemas.** `schemas/` (canonical reference copies) and
   `axis_core/schemas/` (runtime) are byte-identical and are valid JSON Schema
   Draft-07 documents.

3. **Terminology.** Schema field names use the protocol glossary: `proof`,
   `attestation_id`, `decision` (`allowed`, `reason`, …), `oracle_id`,
   `manifest_ref`, `device_id`, `nonce`, `timestamp`, `signature`.

4. **Examples → schema.** `attestation-example.json` and
   `attestation-example-deny.json` validate against `attestation.schema.json`.
   Because the oracle now verifies real device signatures and enforces
   freshness/replay, the live API flow is exercised with dynamically signed
   proofs (the static examples remain illustrative schema documents).

5. **Decision scenarios.** The oracle decision logic is exercised for allowed,
   policy-denied, stale-timestamp, future-timestamp, replay, unregistered-device
   and invalid-signature outcomes.

6. **Provisioning → Registry flow.** Register → attest → read the device record
   end-to-end.

7. **Policy Engine (ADR-0003).** The oracle decision pipeline is split between
   the Verifier (cryptography) and the Policy Engine (`axis_core.policy`),
   which mirrors the on-chain `PolicyEngine` of the ENRG reference
   implementation. `tests/test_policy_engine.py` mirrors the on-chain unit
   tests (mint pause, oracle whitelist, device-state gating, freshness,
   tier limits, energy caps, supply cap).

8. **Trust Envelope (wire format).** `tests/test_wire.py` pins the codec
   guarantees: deterministic serialization, signature over the entire
   envelope, tamper detection, structural validation.

---

## 2. Known deviations and gaps

The following deviations from the protocol-level documents exist in the current
implementation. They are **documented, not silently changed**.

### 2.1. License metadata

- `pyproject.toml` declares SPDX `license = "Apache-2.0"` — consistent with the
  repository `LICENSE` file (Apache 2.0).

### 2.2. Device Manifest vs ADR-0004

`schemas/device_manifest.schema.json` describes a *structural* manifest
(`manifest_id`, `version`, `manufacturer`, `model`, `capabilities`, `constraints`,
`created_at`). ADR-0004 additionally defines *operational* manifest fields
(`trust_level`, `heartbeat_interval`, `proof_threshold`, `policy_version`,
`verifier_endpoint`, `signature`). These are not yet represented.

### 2.3. Device lifecycle states

- Protocol (ADR-0005): `UNREGISTERED, REGISTERED, CLAIMED, PROVISIONED, ACTIVE,
  QUARANTINE, MAINTENANCE, REVOKED`.
- Implementation (`device_record.schema.json`, registry service):
  `provisioned, active, suspended, retired` — a simplified subset.

The registry stores the simplified set for the reference flow.

### 2.4. Wire format

The protocol defines a binary **Trust Envelope** (`spec/protocol/wire-format.md`).
Axis Core now implements a **Trust Envelope codec** (`axis_core.wire`): the
envelope (envelope header + message header + payload) is serialized as
canonical JSON and signed as a whole with Ed25519. The codec is
deterministic, versioned and self-describing.

Known limitation: the current codec is **JSON-based**, not the binary codec
outlined in the specification. Binary encoding (`u8/u16/u32` big-endian,
length-prefixed strings) is a future implementation detail and does not affect
the trust properties (determinism, whole-envelope signature, versioning).

### 2.5. Provisioning API naming

Protocol-level platform documents describe `/identity/register`, `/identity/claim`,
`/identity/status`. The reference implementation exposes
`/provisioning/register` and `/provisioning/attest` (see `API.md`).

### 2.6. Policy engine (mock rules) and signature verification

`POST /oracle/attest` now **verifies real Ed25519 device signatures** (spec
section 12, ADR-0001/ADR-0003). The remaining simplification is the **policy
engine**: allow/deny is based on `max_power_kw` thresholds only (a mock policy
engine); richer policies are future work.

The `mock` algorithm is accepted only when the `AXIS_ALLOW_MOCK` environment
variable is set (`1`/`true`/`yes`) — a documented dev-only mode. By default the
oracle requires `algo = "ed25519"` with a valid signature.

### 2.7. JSON schema `$id` namespace

The schemas previously carried ENRG-specific identifiers
(`https://enrg.energy/...`, `https://enrg.local/...`). They were neutralized to
`https://axisprotocol.org/schemas/...`.

---

## 3. Device signature verification (canonical message)

The oracle verifies device proofs with **Ed25519**. Two encodings are fixed and
normative for this implementation:

- **Device public key** (registered via `POST /provisioning/register`):
  Base64-encoded raw 32-byte Ed25519 public key.
- **Proof signature** (`proof.signature`): Base64-encoded raw 64-byte Ed25519
  signature.

The **canonical signed message** is the UTF-8 encoding of the canonical JSON
serialization of the proof fields *excluding* `signature`:

```json
{"algo":"ed25519","device_id":"...","nonce":"...","payload":{"max_power_kw":2.5},"timestamp":"..."}
```

Canonical JSON means: keys sorted lexicographically, no whitespace, `,` and `:`
separators (the form produced by `axis_core.signature_utils.canonical_proof_message`).
Devices MUST use an equivalent language-agnostic canonical JSON serializer so the
exact byte string matches. The `payload` object is included as-is (sorted
recursively by the canonical serializer). Floats that are exactly integral
(e.g. `2.0`) are normalized to integers (`2`) so `2` and `2.0` produce identical
bytes; all other numbers are serialized as-is.

> **Note on ENRG compatibility.** The ENRG domain profile signs a *binary*
> message (`device_id || nonce LE || timestamp LE || energy_wh LE`, see
> `OracleReport::device_message_to_sign()`). The two formats are intentionally
> different because the identity models differ (string `device_id` here vs
> 32-byte pubkey in ENRG). ENRG can remain on its binary format; Axis Core
> documents the canonical JSON format above as its normative signing scheme.

### Decision reasons

The `decision.reason` values produced by the oracle:

| reason | meaning |
| :--- | :--- |
| `ok` | signature verified, policy allowed |
| `device_not_registered` | `device_id` not found in the registry (Ed25519 path) |
| `signature_invalid` | registered device, but the signature is invalid |
| `unsupported_algo` | unknown `algo` value |
| `mock_disabled` | `algo = "mock"` used without `AXIS_ALLOW_MOCK` |
| `stale_timestamp` | proof `timestamp` older than `MAX_PROOF_AGE_SECONDS` (900 s) |
| `future_timestamp` | proof `timestamp` more than `MAX_CLOCK_SKEW_SECONDS` (300 s) in the future |
| `nonce_replay` | `nonce` was already used by this `device_id` |
| `invalid_timestamp` | `timestamp` missing or not a valid ISO 8601 UTC (`Z`) value |
| `invalid_nonce` | `nonce` missing or empty |
| `max_power_exceeded` | requested `max_power_kw` above the policy limit (5.0 kW) |
| `below_minimum_power` | mock path, requested power below 0.1 kW |

The response shape (`device_id`, `attestation_id`, `decision`, `oracle_id`) and
status codes are unchanged; only new `reason` values were added.

---

### Oracle attestation signature

The oracle **signs** each attestation with its own Ed25519 key (unrelated to any
device key) to certify the outcome of its verification. The signing key is loaded
from the `ORACLE_SECRET_KEY` environment variable (Base64-encoded 32-byte seed).

- The canonical message is the canonical JSON of the attestation **without** the
  `oracle_signature` field (same canonical rules as the proof message).
- The signature is Base64-encoded raw 64-byte Ed25519.
- If `ORACLE_SECRET_KEY` is unset and `AXIS_ALLOW_MOCK` is off, the oracle
  rejects attestation with `503` (`oracle key not configured`). With
  `AXIS_ALLOW_MOCK=1` and no key, a clearly marked `mock-oracle-signature` stub
  is used for development only.

### Freshness and replay policy

- **Freshness:** a proof `timestamp` older than `MAX_PROOF_AGE_SECONDS` (900 s)
  is rejected with `stale_timestamp`; a `timestamp` more than
  `MAX_CLOCK_SKEW_SECONDS` (300 s) in the future is rejected with
  `future_timestamp`. Constants live in `axis_core/config.py`.
- **Replay:** used nonces are tracked per `device_id` in memory
  (`axis_core/oracle_storage.py`). A repeated nonce is rejected with
  `nonce_replay`. The nonce is recorded only after the signature is verified, so
  an attacker cannot "burn" a victim's nonce with an invalid signature.

### Device registration (proof of possession)

`POST /provisioning/register` requires the device to prove it holds the private
key that matches the public key it registers:

- `public_key` must be Base64-encoded 32-byte Ed25519.
- `signature` (Base64-encoded 64-byte Ed25519) over the canonical message
  `{"nonce":...,"public_key":...}` plus a `nonce`.
- In dev mode (`AXIS_ALLOW_MOCK=1`) the signature may be omitted for tooling.

### Legacy Mode A re-verification

The legacy "full Attestation" mode no longer trusts a pre-built document. The
embedded `proof` is re-verified through the same decision pipeline and the
attestation is rebuilt (fresh `decision`, fresh `issued_at`, real
`oracle_signature`). Unverifiable proofs are rejected with `403` and the
`reason` in the response body.

---

## 4. Conformance claim

Axis Core conforms to the Axis Protocol in the following respects:

- proofs and attestations are carried as *self-describing, schema-validated*
  documents;
- the private key never leaves the device (ADR-0001) — no key material exists in
  the core;
- the oracle **verifies** device proofs (it never creates them): it checks the
  registered public key, verifies the Ed25519 signature over the canonical
  message, enforces timestamp freshness and nonce replay protection, applies the
  policy engine, and then signs the resulting attestation with its own key;
- device registration requires proof of possession of the device private key
  (ADR-0001);
- the Device Registry is the single source of truth for device records
  (ADR-0002);
- device identity is deterministic and bound to the public key;
- the oracle decision pipeline follows ADR-0003: the **Verifier** performs the
  cryptography (signature, nonce, registration) and the **Policy Engine**
  (`axis_core.policy`) makes every admissibility decision, mirroring the
  on-chain `PolicyEngine` of the ENRG reference implementation;
- messages can be carried in the **Trust Envelope** wire format
  (`axis_core.wire`): deterministic, versioned, signed as a whole — identity,
  integrity and non-repudiation per `spec/protocol/wire-format.md`;
- the core is platform- and domain-agnostic (no blockchain or domain artifacts).

See the conformance tests in `tests/test_conformance.py` for the exact checks.
