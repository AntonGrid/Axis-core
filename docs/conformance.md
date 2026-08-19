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

### 2.1. License metadata mismatch

- `pyproject.toml` declares `license = "MIT"`.
- The `LICENSE` file in the repository is **Apache 2.0**.

This is a packaging metadata inconsistency. **Not changed in this pass** — it
requires an explicit decision.

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

### 2.6. Oracle decision logic (mock policy engine)

`POST /oracle/attest` applies a **mock policy engine**: allow/deny based on
`max_power_kw` thresholds, with `algo = "mock"` signatures. Real Ed25519 signature
verification (spec section 12, ADR-0001/ADR-0003) is not yet enforced in the API
layer — the core never holds private keys, but the verification pipeline is not
wired to the schema validation yet.

### 2.7. JSON schema `$id` namespace

The schemas previously carried ENRG-specific identifiers
(`https://enrg.energy/...`, `https://enrg.local/...`). They were neutralized to
`https://axisprotocol.org/schemas/...`.

---

## 3. Conformance claim

Axis Core conforms to the Axis Protocol in the following respects:

- proofs and attestations are carried as *self-describing, schema-validated*
  documents;
- the private key never leaves the device (ADR-0001) — no key material exists in
  the core;
- the oracle **verifies** inputs and issues decisions; it does not create device
  proofs;
- the Device Registry is the single source of truth for device records
  (ADR-0002);
- device identity is deterministic and bound to the public key;
- the core is platform- and domain-agnostic (no blockchain or domain artifacts).

See the conformance tests in `tests/test_conformance.py` for the exact checks.
