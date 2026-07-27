# Axis / ENRG JSON Schemas (v1.0)

This document summarizes the JSON schemas used in the ENRG / Axis prototype and how they map to API endpoints.

## Versioning

All primary JSON types are versioned via a top-level field:

```json
{
  "schema_version": "1.0",
  "..."
}
Current stable version: 1.0
New major changes MUST bump schema_version (e.g. "2.0") and live in new schemas (e.g. *_v2.schema.json), while API handlers should explicitly accept both when needed.
Schemas overview
Type	Schema file	Required schema_version	Used by
Attestation	schemas/attestation.schema.json	"1.0"	/oracle/attest (legacy attestation mode)
DeviceManifest	schemas/device_manifest.schema.json	"1.0"	Provisioning/registry services (off-chain only)
DeviceRecord	schemas/device_record.schema.json	"1.0"	Registry service (off-chain only)
DeviceProof	schemas/device_proof.schema.json	"1.0"	/provisioning/attest
OracleAttestReq	schemas/oracle_attest_request.schema.json	"1.0"	/oracle/attest (new oracle request mode)
Attestation (legacy)
Schema: schemas/attestation.schema.json
API: POST /oracle/attest (legacy mode, when body looks like a full attestation)

Required top-level fields (simplified):

schema_version: "1.0"
attestation_id: string
device_id: string
oracle_id: string
issued_at: string (ISO 8601)
decision: object
proof: object
oracle_signature: string
Server-side rules:

Schema is validated strictly.
schema_version is required and must be "1.0".
issued_at is additionally validated as ISO 8601 timestamp.
DeviceManifest (1.0)
Schema: schemas/device_manifest.schema.json
Canonical example: device-manifest-example.json

Minimal shape:

{
  "schema_version": "1.0",
  "manifest_id": "urn:enrg:manifest:basic-sensor-v1",
  "version": "1.0.0",
  "manufacturer": "ENRG Labs",
  "model": "ENRG-Node-100",
  "hardware_revision": "revA",
  "firmware_version": "1.0.3",
  "capabilities": ["energy-metering", "signature-reporting"],
  "constraints": {
    "max_power_kw": 5.0,
    "min_power_kw": 0.0
  },
  "created_at": "2026-07-25T10:00:00Z"
}
DeviceRecord (1.0)
Schema: schemas/device_record.schema.json
Canonical example: device-record-example.json
API: Registry service (off-chain), typically exposed as GET /registry/devices/{device_id}.

Minimal shape:

{
  "schema_version": "1.0",
  "device_id": "dev_0123abcd4567ef89",
  "public_key": "ed25519:...",
  "owner": "did:example:org-enrg-lab-1",
  "lifecycle_state": "active",
  "firmware_version": "1.0.3",
  "manifest_ref": "urn:enrg:manifest:basic-sensor-v1",
  "created_at": "2026-07-25T12:10:00Z",
  "updated_at": "2026-07-25T12:20:00Z",
  "labels": {
    "site": "berlin-dc1",
    "env": "prod"
  }
}
DeviceProof (1.0)
Schema: schemas/device_proof.schema.json
Canonical examples (repo root):

device-proof-provisioning.json
device-proof-bootstrap.json
device-proof-attestation.json
API: POST /provisioning/attest

Minimal valid shape:

{
  "schema_version": "1.0",
  "device_id": "dev_0123abcd4567ef89",
  "nonce": "random-nonce",
  "timestamp": "2026-07-25T12:30:00Z",
  "algo": "mock",
  "payload": {
    "...": "arbitrary device payload, e.g. state/metrics/context"
  },
  "signature": "hex-or-base-encoded-signature"
}
Server-side behavior:

If schema_version is missing, the API currently defaults it to "1.0" for backward compatibility.
Device id is checked against the in-memory registry; if device is unknown, API returns 400 with:
detail.message = "Invalid DeviceProof"
detail.path = ["device_id"].
Oracle Attest Request (1.0)
Schema: schemas/oracle_attest_request.schema.json
API: POST /oracle/attest (new request/decision mode)

Minimal valid shape:

{
  "schema_version": "1.0",
  "device_id": "dev_0123abcd4567ef89",
  "nonce": "abc12345xyz",
  "timestamp": "2026-07-25T19:00:00Z",
  "algo": "mock",
  "payload": {
    "max_power_kw": 2.5
  },
  "signature": "deadbeef..."
}
Server-side behavior (new mode):

If schema_version is missing, the API defaults to "1.0" before schema validation.
Timestamp is additionally validated as ISO 8601 string with Z suffix.
Oracle computes a simple decision:
If max_power_kw > 5.0: allowed = false, reason = "max_power_exceeded".
Else: allowed = true, reason = "ok".
Result is stored in in-memory _ATTESTATIONS with a generated attestation_id.

Backward compatibility notes
Legacy Attestation (full object with proof/decision/oracle_id/...) is still supported on /oracle/attest and strictly requires schema_version: "1.0".
DeviceProof and OracleAttestRequest APIs are tolerant to missing schema_version and auto-default it to "1.0".
Example JSONs in examples/ may represent legacy or experimental formats and are not guaranteed to validate against the current 1.0 schemas; for canonical shapes, use the examples in the repo root
