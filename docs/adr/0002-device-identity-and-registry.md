# 0002 – Device Identity and Registry (Part II)

*Status*: Draft  
*Date*: 2026-07-25  
*Authors*: Architecture Working Group

## Context

Axis Core needs a clear, verifiable, and chain‑ready model for **device
identity**, as well as a single source of truth for device lifecycle and
state.

This ADR defines:

- the trust model for device identity
- the main components in the identity path
- core data artifacts and identifiers

It is the foundation for:

- Policy Engine (PE)
- Oracle (OR)
- Smart Contract (SC) and on‑chain governance flows

## Decision

### 1. Root of Trust

- Each device generates its own **Ed25519** keypair.
- The **private key never leaves the device**.
- The **public key** is exposed and used in:
  - device manifest
  - device record
  - proof / attestation verification

### 2. Identifiers

- `device_id`: deterministic identifier derived from the device public key
  and stable attributes. Current format: **base58**, length 32–64.
- `manifest_id`: identifier of a device manifest (definition), format: **base58**.
- `manifest_ref`: reference to `manifest_id` stored in device records and proofs.

These constraints are encoded in JSON Schemas:

- `schemas/device-manifest.schema.json`
- `schemas/device-record.schema.json`
- `schemas/device-proof.schema.json`

### 3. Core Components

We define the following components for the identity and registry path:

- **Device** – physical or virtual device holding the private key.
- **Provisioning Service (PS)** – first contact point for the device, verifies
  proofs and creates/updates records in the Device Registry.
- **Device Registry (DR)** – single source of truth for:
  - device identity (`device_id`, `public_key`)
  - lifecycle state
  - linkage to manifests
- **Policy Engine (PE)** – evaluates policies based on device state and proofs.
- **Oracle (OR)** – off‑chain verification and aggregation, signs attestations
  for on‑chain or external consumption.
- **Smart Contract (SC)** – minimal on‑chain surface:
  - validates oracle attestations
  - reflects device state relevant to the chain
- **Governance component (e.g. DAO)** – governs trusted oracles and policies.

Interaction flow (high level):

`Device → PS → DR → PE → OR → SC → Governance`

### 4. Data Artifacts

We standardize three main artifacts:

1. **DeviceManifest**
   - Describes device model, manufacturer, hardware/firmware baseline, capabilities.
   - Has a stable `manifest_id`.
   - One manifest can be referenced by many device records.

2. **DeviceRecord**
   - Per‑device record in the Device Registry.
   - Contains:
     - `device_id`
     - `public_key`, `key_type`
     - `manifest_ref`
     - `lifecycle_state`
     - firmware information, timestamps, tags, metadata

3. **DeviceProof**
   - A signed payload from the device, used for:
     - `provisioning`
     - `bootstrap`
     - `attestation` (regular operation)
   - Contains:
     - `type` (provisioning | bootstrap | attestation)
     - `device_id`, `manifest_ref`
     - `nonce` (anti‑replay)
     - `timestamp`
     - `payload` (firmware, state, metrics, context)
     - `signature`, `signature_algorithm` (Ed25519)

All three artifacts are validated against JSON Schemas in `schemas/`.

### 5. API Surface (OpenAPI 3.0.3)

We define a combined OpenAPI spec for the Provisioning Service and Device Registry:

- File: `openapi/provisioning-registry.yaml`
- Uses external `$ref` to schemas in `../schemas/`.

Key endpoints:

- `POST /manifests` – create/register a manifest.
- `GET /manifests/{manifest_id}` – get manifest.
- `POST /devices` – initial provisioning via `DeviceProof` of type `provisioning`.
- `GET /devices/{device_id}` – retrieve `DeviceRecord`.
- `POST /devices/{device_id}/bootstrap` – bootstrap proof.
- `POST /devices/{device_id}/attestations` – regular attestation proof.

This API is **off‑chain**, but its contracts are stable and chain‑ready:

- Oracle and PE can rely on the Device Registry as a source of truth.
- On‑chain SC only needs attestations from the Oracle, not the full artifacts.

### 6. Trust Model

- Trust anchor: **private key on the device**.
- Device Registry is trusted to:
  - store and expose correct mappings (`device_id → public_key` etc.)
  - maintain lifecycle status.
- Policy Engine and Oracle are trusted to:
  - interpret proofs and registry state
  - return ALLOW / DENY / CHALLENGE / QUARANTINE decisions (PE)
  - publish attestations for on‑chain or external usage (OR).
- The smart contract only trusts:
  - whitelisted oracles (managed by governance)
  - correct signature schemes and formats.

Replays are mitigated via:

- `nonce` and `timestamp` in `DeviceProof`
- verification logic in PS / PE / OR (detailed mechanisms are out of scope for
  this ADR and will be covered separately).

### 7. Scope

This ADR fixes:

- Identifier formats and their usage.
- The set of identity‑related components and their responsibilities.
- The three core schemas and their purpose.
- The minimal off‑chain API surface to support provisioning and registry.

Out of scope (to be covered in follow‑up ADRs):

- Full policy language and PE implementation details.
- Oracle‑to‑chain attestation format and SC ABI.
- Detailed nonce and replay protection mechanisms.
- Migration strategies for existing devices.

## Consequences

### Positive

- Clear separation of concerns:
  - Device ↔ PS ↔ DR ↔ PE ↔ OR ↔ SC ↔ Governance.
- Extensible, as schemas and APIs are explicit and versioned.
- Suitable for deployments where an on‑chain component is present, with a
  minimal on‑chain surface.
- Reuse: manifests and proofs are reusable across pilots, vendors, and
  different higher‑level platforms.

### Negative / Risks

- Additional complexity from multiple components (PS, DR, PE, OR).
- Need for robust key management and secure key generation on devices.
- Tight coupling between Device Registry availability and overall system
  behavior.

### Alternatives Considered

1. **Centralized provisioning without a public registry**
   - Simpler, but no single source of truth; weak basis for on‑chain or
     cross‑system verification.

2. **Direct device‑to‑chain registration**
   - Too heavy and complex for constrained devices.
   - Difficult upgrades and governance.

## Next Steps

- Finalize and version the JSON Schemas (e.g. draft‑07).
- Validate the OpenAPI spec against tooling (e.g. swagger‑cli).
- Implement a reference Provisioning Service and Device Registry using these
  contracts.
- Prepare follow‑up ADRs, e.g.:
  - `0003-policy-engine-and-oracle`
  - `0004-on-chain-attestations-and-governance`
