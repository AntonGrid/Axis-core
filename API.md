# Axis Core — API Overview

This document describes the public HTTP API exposed by the Axis Core backend.
It is a minimal, consistent, and schema-aligned description of the endpoints
that participate in the provisioning → attestation → on-chain flow.

All request/response payloads are JSON and are validated against the JSON Schemas
in `axis_core/schemas/` (runtime) and `schemas/` (reference copies).

Base URL (default): `http://localhost:8000`

---

## 1. Health

**Endpoint:** `GET /health`

**Description:** Simple liveness probe for the backend.

**Response:**

```json
{
  "status": "ok"
}
```

---

## 2. Provisioning

### 2.1. `POST /provisioning/register`

Register a new device. Accepts the device public key (Base64-encoded Ed25519)
and an optional manifest reference, and returns a deterministic `device_id`,
the assigned `manifest_ref`, and the bootstrap policy.

**Request:**

```json
{
  "public_key": "<base64-ed25519-public-key>",
  "manifest_ref": "manifest:v0-placeholder",
  "signature": "<base64-ed25519-signature>",
  "nonce": "<nonce>"
}
```

`signature` is the Base64-encoded Ed25519 proof-of-possession over the canonical
message `{"nonce":...,"public_key":...}`. In dev mode (`AXIS_ALLOW_MOCK=1`) the
`signature`/`nonce` may be omitted.

**Response (200):**

```json
{
  "device_id": "dev_9e9c644e1580a83b",
  "manifest_ref": "manifest:v0-placeholder",
  "bootstrap_policy": {
    "allowed": true,
    "max_power_kw": 3.5
  }
}
```

**Error (400):** missing/invalid `public_key`, missing proof-of-possession
(`signature` + `nonce`), or an invalid PoP signature.

### 2.2. `POST /provisioning/attest`

Accept a `DeviceProof` (validated against `device_proof.schema.json`) and return
a simple decision. If the device is not registered, the request is rejected.

**Request:**

```json
{
  "schema_version": "1.0",
  "device_id": "dev_9e9c644e1580a83b",
  "nonce": "abc12345xyz",
  "timestamp": "2026-07-25T19:00:00Z",
  "algo": "mock",
  "payload": { "max_power_kw": 2.5 },
  "signature": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
}
```

**Response (200):**

```json
{
  "status": "ok",
  "device_id": "dev_9e9c644e1580a83b",
  "decision": {
    "allowed": true,
    "reason": "mock-allowed"
  }
}
```

**Error (400):** invalid `DeviceProof` or device not registered.

---

## 3. Device Registry

### 3.1. `GET /registry/devices/{device_id}`

Retrieve a device record by its ID.

**Response (200):**

```json
{
  "device_id": "dev_9e9c644e1580a83b",
  "public_key": "<base64-ed25519-public-key>",
  "owner": null,
  "lifecycle_state": "provisioned",
  "firmware_version": null,
  "manifest_ref": "manifest:v0-placeholder"
}
```

**Error (404):** device not found.

---

## 4. Oracle

### 4.1. `POST /oracle/attest`

The oracle endpoint works in two modes.

#### Mode A: Full Attestation (legacy)

Accepts a complete Attestation document, validates it against
`attestation.schema.json`, then **re-verifies the embedded device proof**
(signature + freshness/replay + policy). The attestation is re-signed by the
oracle and stored only if the proof is valid. Unverifiable proofs are rejected
with `403` and a `reason`.

**Request:**

```json
{
  "schema_version": "1.0",
  "attestation_id": "att_123",
  "device_id": "dev_9e9c644e1580a83b",
  "proof": { "...": "..." },
  "decision": { "allowed": true, "reason": "ok", "max_power_kw": 2.5 },
  "oracle_id": "oracle_main_1",
  "issued_at": "2026-07-25T19:05:00Z",
  "oracle_signature": "..."
}
```

**Response (200):**

```json
{
  "status": "received",
  "attestation_id": "att_123",
  "device_id": "dev_9e9c644e1580a83b",
  "oracle_id": "oracle_main_1"
}
```

**Error (400):** schema validation error (`"Validation error: ..."`).

**Error (403):** the embedded proof is unverifiable — response body
`{"detail": {"reason": "<reason>"}}`.

#### Mode B: Attestation request (new format)

Accepts an `oracle_attest_request` (`device_id`, `nonce`, `timestamp`, `algo`,
`payload`, `signature`), validates it against `oracle_attest_request.schema.json`,
**verifies the device Ed25519 signature** against the registered public key, then
applies the decision logic (a mock policy engine).

**Request:**

```json
{
  "device_id": "dev_9e9c644e1580a83b",
  "nonce": "abc12345xyz",
  "timestamp": "2026-07-25T19:05:00Z",
  "algo": "ed25519",
  "payload": { "max_power_kw": 2.5 },
  "signature": "<base64-ed25519-signature>"
}
```

**Response (200):**

```json
{
  "device_id": "dev_9e9c644e1580a83b",
  "attestation_id": "a6ff7c9a-9e75-4f6c-9b18-2cbb2e9b1a77",
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 2.5
  },
  "oracle_id": "oracle_main_1"
}
```

**Decision reasons:** `ok`, `device_not_registered`, `signature_invalid`,
`unsupported_algo`, `mock_disabled`, `stale_timestamp`, `future_timestamp`,
`nonce_replay`, `invalid_timestamp`, `invalid_nonce`, `max_power_exceeded`,
`below_minimum_power` (see `docs/conformance.md`).

The oracle signs each attestation with its own Ed25519 key loaded from
`ORACLE_SECRET_KEY` (Base64-encoded 32-byte seed). If it is unset and
`AXIS_ALLOW_MOCK` is off, the endpoint returns `503`.

**Errors (400):**

- schema validation error: `"Validation error: ..."`;
- missing required field: `"Missing required field: 'signature'"`;
- invalid timestamp: `"timestamp must end with 'Z'"`.

The `timestamp` must be in ISO 8601 UTC format with a trailing `Z`, for example
`2026-07-25T19:05:00Z`. The `attestation_id` is generated by the server (UUID).

### 4.2. `GET /oracle/attestations` and `GET /oracle/attestations/{attestation_id}`

List stored attestations (paginated) and retrieve a specific attestation by ID.

### 4.3. `GET /oracle/requests` and `GET /oracle/requests/{request_id}`

List stored oracle requests (paginated) and retrieve a specific request by ID.

---

## 5. Attestation and on-chain bridge

The backend exposes building blocks rather than a single `/attestation` endpoint:

- `/oracle/attest` — makes a decision (allowed / deny);
- `axis_core.onchain_bridge.build_attestation_params(attestation)` — converts a JSON
  Attestation into on-chain parameters suitable for a Solidity function:

```solidity
function submitAttestation(
  bytes32 attestationId,
  bytes32 deviceId,
  bool allowed,
  uint64 maxPowerW,
  uint64 issuedAt
)
```

The demo scripts in `scripts/` illustrate how to go from:

- raw oracle response → full Attestation (`schema_version: "1.0"`);
- Attestation JSON → on-chain parameters;
- on-chain parameters → ABI-encoded calldata for `submitAttestation(...)`.

For full details on the Attestation JSON shape, see `SCHEMAS.md` and
`schemas/attestation.schema.json`.
