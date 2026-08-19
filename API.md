# Axis Core — API Overview

This document describes the public HTTP API exposed by the Axis Core backend.
The goal is to provide a minimal, consistent, and schema-aligned description
of the endpoints that participate in the attestation → on-chain flow.

All request/response payloads are JSON and are validated against the JSON Schemas
in `axis_core/schemas/` (runtime) and `schemas/` (reference copies).

Base URL (default):

- `http://localhost:8000`

---

## 1. Health

**Endpoint**

- `GET /health`

**Description**

Simple liveness probe for the backend.

**Response**

```json
{
  "status": "ok"
}
2. Oracle attest
Endpoint

POST /oracle/attest

Description

Evaluate whether a given device is allowed to operate under a requested configuration (e.g. requested power). This is the main entry point for the oracle decision.

Request body

Validated by axis_core/schemas/oracle_attest_request.schema.json.

Typical example:

json
{
  "device_id": "dev_demo_full_cycle",
  "nonce": "demo_nonce_123",
  "max_power_kw": 3.3
}
Field summary:

device_id (string, required) — Unique identifier of the device, must be consistent across API calls and on-chain mapping.

nonce (string, required) — Client-provided nonce for replay protection / correlation. In demos this is a human-readable string.

max_power_kw (number, required) — Requested maximum power in kW.

Response body

Simplified structure (validated by the same-family schema):

json
{
  "device_id": "dev_demo_full_cycle",
  "attestation_id": "661a8435-b9ec-4722-8654-c92ef0e172e5",
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 3.3
  },
  "oracle_id": "oracle_main_1"
}
For deny cases, the decision may look like:

json
"decision": {
  "allowed": false,
  "reason": "max_power_exceeded",
  "max_power_kw": 10.0,
  "limit_kw": 5.0
}
Field summary:

device_id (string) – echoed from request.

attestation_id (string, UUID) – logical identifier of this oracle decision.

decision (object):

allowed (boolean) – whether the device is allowed under the requested conditions.

reason (string) – short, human-readable explanation.

max_power_kw (number) – effective max power in kW for this decision.

limit_kw (number, optional, deny only) – configured limit that was exceeded.

oracle_id (string, optional) – identifier of the oracle instance.

This response is not yet the final Attestation, but it contains enough information to build one (see attestation.schema.json and demos).

3. Provisioning / bootstrap endpoints
Note: exact paths and payload details depend on your current implementation. Below is a high-level outline aligned with the JSON schemas.

These endpoints handle device provisioning and proofs, validated against:

schemas/device_manifest.schema.json

schemas/device_proof.schema.json

schemas/device_record.schema.json

Typical roles:

Device Manifest — Static description of device capabilities and identifiers.

Device Proof (bootstrap / provisioning) — Cryptographic material or structured evidence that a device is genuine and bound to a certain identity.

Device Record — Aggregated, persistent record the protocol keeps about a device (manifest + proofs + state).

If you expose HTTP endpoints like /provisioning/manifest, /provisioning/proof, etc., their payloads should follow the above schemas. The detailed field-level specification lives in SCHEMAS.md.

4. Attestation and on-chain bridge
The backend does not necessarily expose a /attestation HTTP endpoint; instead, it exposes building blocks:

/oracle/attest — makes a decision (allowed / deny).

Local utilities — build a full Attestation document from oracle responses.

axis_core.onchain_bridge.build_attestation_params(attestation) — converts a JSON Attestation into on-chain parameters suitable for a Solidity function:

solidity
function submitAttestation(
  bytes32 attestationId,
  bytes32 deviceId,
  bool allowed,
  uint64 maxPowerW,
  uint64 issuedAt
)
The demo scripts in `scripts/` illustrate how to go from:

Raw oracle response → full Attestation (schema_version: "1.0").

Attestation JSON → on-chain parameters.

On-chain parameters → ABI-encoded calldata for submitAttestation(...).

For full details on the Attestation JSON shape, see SCHEMAS.md and schemas/attestation.schema.json.
