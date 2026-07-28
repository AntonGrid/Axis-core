# Axis Core — JSON Schemas

This document describes the purpose and key fields of the JSON Schemas used
in the Axis Core project. The canonical schema files live in the `schemas/` directory.
Runtime validation typically uses copies in `app/schemas/`.

All Attestation-related flows are aligned on `schema_version: "1.0"`.

---

## 1. Attestation (`schemas/attestation.schema.json`)

**Purpose**

Represents a complete, signed Attestation that can be used to drive on-chain
decisions (through the on-chain bridge).

**Minimal example (allow)**

```json
{
  "schema_version": "1.0",
  "attestation_id": "661a8435-b9ec-4722-8654-c92ef0e172e5",
  "device_id": "dev_demo_full_cycle",
  "proof": {
    "device_id": "dev_demo_full_cycle",
    "nonce": "demo_nonce_123",
    "timestamp": "2026-07-27T05:34:03Z",
    "algo": "mock",
    "payload": {
      "max_power_kw": 3.3
    },
    "signature": "deadbeefdeadbeef..."
  },
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 3.3
  },
  "oracle_id": "oracle_main_1",
  "issued_at": "2026-07-27T05:34:03Z",
  "oracle_signature": "cafebabecafebabe..."
}
Minimal example (deny) — see attestation-example-deny.json.

Key fields

schema_version (string, required) — Must be "1.0" for this version of the schema.

attestation_id (string, required) — Logical identifier of the attestation; usually matches the oracle’s attestation_id.

device_id (string, required) — Device identifier, consistent with /oracle/attest and on-chain encoding.

proof (object, required) — Device-level proof. Structure is intentionally flexible but includes:

device_id (string)

nonce (string)

timestamp (RFC3339/ISO 8601 string, UTC, e.g. 2026-07-27T05:34:03Z)

algo (string) – algorithm or proof type, "mock" in demos.

payload (object) – e.g. { "max_power_kw": 3.3 }

signature (string) – opaque hex/string signature.

decision (object, required)

allowed (boolean) – whether the device is allowed.

reason (string) – human-readable explanation.

max_power_kw (number) – effective limit in kW.

Additional fields (like limit_kw) may appear in oracle responses, but the Attestation schema focuses on the effective outcome.

oracle_id (string, required) — Identifier of the oracle instance.

issued_at (string, required) — RFC3339/ISO 8601 timestamp of when the oracle issued this attestation.

oracle_signature (string, required) — Oracle’s signature over the attestation content (opaque for the schema).

This document is what app.onchain_bridge.build_attestation_params() consumes.

2. Oracle attest request (schemas/oracle_attest_request.schema.json)
Purpose

Validates requests sent to POST /oracle/attest.

Example

json
{
  "device_id": "dev_demo_full_cycle",
  "nonce": "demo_nonce_123",
  "max_power_kw": 3.3
}
Key fields

device_id (string, required) — Device identifier, must be stable and unique.

nonce (string, required) — Client nonce for replay protection / correlation.

max_power_kw (number, required) — Requested maximum power in kW.

The corresponding oracle response is structurally compatible but is not itself a full Attestation (no schema_version, no full proof or oracle_signature).

3. Device manifest (schemas/device_manifest.schema.json)
Purpose

Describes static properties and capabilities of a device.

Example (abridged)

json
{
  "schema_version": "1.0",
  "device_id": "dev_demo_001",
  "manufacturer": "Example Inc.",
  "model": "X-1000",
  "capabilities": {
    "max_power_kw": 5.0
  }
}
Typical fields:

schema_version (string) – version of the manifest schema, "1.0" in this repo.

device_id (string) – unique device identifier.

manufacturer, model (strings) – device metadata.

capabilities (object) – structured technical capabilities (e.g. maximum power).

4. Device proof (schemas/device_proof.schema.json)
Purpose

Represents cryptographic evidence or other structured proof used during device bootstrap or provisioning.

There may be multiple flavors of proofs (bootstrap, attestation, provisioning); the schema ensures they all share a consistent core structure.

Typical fields:

schema_version (string)

device_id (string)

nonce (string)

timestamp (string, RFC3339)

algo (string) – algorithm used for the proof.

payload (object) – algorithm-specific payload.

signature (string) – proof signature.

Example documents:

device-proof-bootstrap.json

device-proof-attestation.json

device-proof-provisioning.json

5. Device record (schemas/device_record.schema.json)
Purpose

Aggregated record that the protocol keeps about a device, combining:

basic identity fields,

manifest information,

proofs,

potentially derived state.

Example (very abridged)

json
{
  "schema_version": "1.0",
  "device_id": "dev_demo_001",
  "manifest": { "...": "..." },
  "proofs": [
    { "...": "..." }
  ]
}
Field details depend on your implementation, but the schema enforces:

presence of device_id,

presence of a manifest-like block,

an array of proofs.

Reference example lives in device-record-example.json.

6. Runtime schemas (app/schemas/*.json)
The app/schemas/ directory contains runtime copies of the schemas used for:

validating incoming HTTP requests,

validating constructed Attestation documents during demos.

They should stay in sync with the reference schemas in schemas/.

Key files:

app/schemas/attestation.schema.json

app/schemas/oracle_attest_request.schema.json

The demo scripts (scripts/*.py, onchain/scripts/*.py) use these schemas to validate that everything they send/build is consistent with schema_version: "1.0" and the on-chain bridge expectations.
