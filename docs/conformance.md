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

4. **Examples → schema → API.** `attestation-example.json` and
   `attestation-example-deny.json` validate against `attestation.schema.json` and
   round-trip through `POST /oracle/attest` (allowed and denied scenarios).

5. **Decision scenarios.** The oracle decision logic is exercised for both
   outcomes: allowed (`max_power_kw` within limits) and denied
   (`max_power_exceeded`, `limit_kw` returned).

6. **Provisioning → Registry flow.** Register → attest → read the device record
   end-to-end.

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
The current reference implementation exposes a JSON REST API. A binary envelope
codec is not implemented yet.

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
recursively by the canonical serializer).

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
| `max_power_exceeded` | requested `max_power_kw` above the policy limit (5.0 kW) |
| `below_minimum_power` | mock path, requested power below 0.1 kW |

Public API semantics are unchanged: the response shape
(`device_id`, `attestation_id`, `decision`, `oracle_id`) and status codes remain
the same; only new `reason` values were added.

---

## 4. Conformance claim

Axis Core conforms to the Axis Protocol in the following respects:

- proofs and attestations are carried as *self-describing, schema-validated*
  documents;
- the private key never leaves the device (ADR-0001) — no key material exists in
  the core;
- the oracle **verifies** device proofs: it checks the registered public key,
  verifies the Ed25519 signature over the canonical message, and only then
  applies the policy engine (it never creates device proofs);
- the Device Registry is the single source of truth for device records
  (ADR-0002);
- device identity is deterministic and bound to the public key;
- the core is platform- and domain-agnostic (no blockchain or domain artifacts).

See the conformance tests in `tests/test_conformance.py` for the exact checks.
