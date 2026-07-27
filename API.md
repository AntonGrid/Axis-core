# ENRG / Axis API quick reference

## Base URL

By default (local dev): `http://127.0.0.1:8000`

Run server:

```bash
uvicorn app.main:app --reload
1. Provisioning
1.1 Register device
POST /provisioning/register

Registers a device with its public key and returns a device_id and bootstrap policy.

Request body:

{
  "public_key": "test-public-key-456"
}
Optional fields:

manifest_ref: string – link/URN to a DeviceManifest.
proof: object – DeviceProof (not required in current tests).
Response (200):

{
  "device_id": "dev_xxx",
  "manifest_ref": "urn:enrg:manifest:basic-sensor-v1",
  "bootstrap_policy": {
    "...": "implementation-defined"
  }
}
1.2 Device attestation (DeviceProof)
POST /provisioning/attest

Accepts a DeviceProof and returns a simple mock decision.

Request body (DeviceProof 1.0):

{
  "schema_version": "1.0",
  "device_id": "dev_xxx",
  "nonce": "abc12345xyz",
  "timestamp": "2026-07-25T19:00:00Z",
  "algo": "mock",
  "payload": {
    "max_power_kw": 2.5
  },
  "signature": "deadbeef..."
}
Notes:

schema_version is required by schema but the endpoint defaults to "1.0" if omitted (backward compatible).
device_id must match a known device from /provisioning/register, otherwise:
HTTP 400, with detail.message = "Invalid DeviceProof" and detail.path = ["device_id"].
Response (200):

{
  "status": "ok",
  "device_id": "dev_xxx",
  "decision": {
    "allowed": true,
    "reason": "mock-allowed"
  }
}
Curl example:

curl -X POST http://127.0.0.1:8000/provisioning/attest \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "device_id": "dev_xxx",
    "nonce": "abc12345xyz",
    "timestamp": "2026-07-25T19:00:00Z",
    "algo": "mock",
    "payload": {"max_power_kw": 2.5},
    "signature": "deadbeefdeadbeefdeadbeefdeadbeef"
  }'
2. Oracle
2.1 Legacy Attestation mode
POST /oracle/attest (body looks like full Attestation)

Used mainly by tests and legacy/demo flows. Body must conform to attestation.schema.json.

Key requirements:

schema_version: "1.0" – mandatory, no defaulting.
attestation_id, device_id, oracle_id, issued_at, decision, proof, oracle_signature.
On success returns:

{
  "status": "received",
  "attestation_id": "...",
  "device_id": "...",
  "oracle_id": "..."
}
2.2 New request/decision mode (OracleAttestRequest)
POST /oracle/attest (body looks like request with device_id/nonce/timestamp/...)

Accepts a oracle_attest_request payload and returns a decision. Used in tests/test_oracle_attest.py and in on-chain bridge demos.

Request body (OracleAttestRequest 1.0):

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
Notes:

If schema_version is missing, endpoint defaults to "1.0" before schema validation.
timestamp must be ISO 8601 with Z suffix, otherwise 400 with schema_validation_error.
Response (200):

{
  "device_id": "dev_0123abcd4567ef89",
  "attestation_id": "uuid-generated",
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 2.5
  }
}
Decision rule:

if max_power_kw > 5.0 → allowed = false, reason = "max_power_exceeded";
else → allowed = true, reason = "ok".
Curl example:

curl -X POST http://127.0.0.1:8000/oracle/attest \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "device_id": "dev_0123abcd4567ef89",
    "nonce": "abc12345xyz",
    "timestamp": "2026-07-25T19:00:00Z",
    "algo": "mock",
    "payload": {"max_power_kw": 2.5},
    "signature": "deadbeefdeadbeefdeadbeefdeadbeef"
  }'
2.3 Fetch stored attestation/result
GET /oracle/attestations/{attestation_id}

Returns the original stored object:

For legacy mode: full Attestation.
For new mode: { "request": {..}, "result": {..} }.
If not found → 404.

3. Registry (if enabled in this repo)
Typical pattern:

GET /registry/devices/{device_id} → returns DeviceRecord 1.0 (see device-record-example.json).
Implementation lives in app/services/* and may be stubbed/mocked in this prototype.
