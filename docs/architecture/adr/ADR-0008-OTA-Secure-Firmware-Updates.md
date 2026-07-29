# ADR-0008: OTA & Secure Firmware Updates

Status: Draft  
Date: 2026-07-17  
Authors: Architecture Team  
Related: ADR-0007-Security-Key-Management, docs/registry, firmware/

## Context / Background

Typical constrained hardware platforms (for example, Wi‑Fi–capable microcontrollers with an optional secure element) require a secure mechanism for delivering and installing firmware updates. The update process must ensure:

- integrity and authenticity of firmware images,
- protection of private keys and other sensitive material,
- minimization of the risk of rendering the device unusable (bricking),
- the ability to roll back to a previous working image in case of failures,
- a consistent way to announce, coordinate and audit updates across the fleet.

Without a strict OTA model and a clear trust architecture, the following risks appear:

- installation of tampered or unsigned firmware images,
- inability to roll back to a known‑good version after a failed update,
- fleet‑wide inconsistency between the registry of approved firmware and the actual firmware running on devices,
- difficulty in auditing which software is running on which devices at any given time.

This ADR defines a generic, vendor‑neutral approach to secure OTA firmware updates that can be applied across different device types and implementations.

## Decision

### High-level summary

- Firmware images are signed by a dedicated Firmware Signing Key (for example, using Ed25519, stored offline/cold).  
- A **Firmware Manifest** contains metadata (version, hash, compatibility, policies, signatures) and is published to a Manifest Registry (see ADR-0007).  
- Transport for firmware distribution uses secure channels (e.g., TLS 1.3 over HTTPS, CoAP+DTLS, or MQTT over TLS).  
- Devices:
  - retrieve and verify the manifest,
  - validate the image hash and signatures,
  - check compatibility and policy,
  - only then proceed with installation.
- Installation is designed to be **atomic**:
  - dual‑bank (A/B) or
  - verified‑boot with a *pending* flag and automatic **fallback** if the update fails during a probation window.
- Anti‑rollback is enforced using:
  - hardware‑backed monotonic counters or secure version storage in a secure element (preferred when available),
  - or software‑based mechanisms with clearly understood limitations where hardware support is absent.
- Notifications about new firmware versions can be:
  - **push‑based** (notification service sends signed update notifications), or
  - **pull‑based** (devices poll the Manifest Registry).
- Emergency updates are supported via:
  - an `emergency` flag in the manifest,
  - accelerated publication and distribution paths,
  - explicit prioritization on devices.

### Firmware Manifest format (required fields)

The Firmware Manifest is the canonical description of a firmware release. At minimum, it MUST include:

- `firmware_version`: semver-like string (e.g., `"1.2.3"` or `"2026.07.20"`)
- `image_hash`: `sha256:<hex>`
- `image_size`: integer (bytes)
- `compatible_models`: array of strings (device model identifiers)
- `min_attestation_policy`: string (identifier or URI of the smoke‑tests/verification policy)
- `firmware_signature`: Base64‑encoded signature (e.g., Ed25519) over the canonical manifest or the firmware image, as defined by the signing policy
- `issued_by`: identifier of the signing entity
- `issued_at`: ISO 8601 timestamp
- `emergency`: boolean (default `false`)
- optional `rollout_policy`: object describing rollout strategy (`percentage`, `regions`, `schedule`, etc.)

The manifest is published in the Manifest Registry and can be verified and anchored according to the security and audit model defined in ADR-0007 (for example, via Merkle proofs or other audit mechanisms).

### Update discovery and validation flow

1. **Manifest discovery**
   - **Push model (optional)**: a notification service sends a signed message containing the manifest ID or URI to the device.
   - **Pull model**: the device periodically queries the Manifest Registry, e.g.:

     ```text
     GET /manifests?model=<device-model-id>
     ```

2. **Manifest verification on the device**
   - The device verifies the manifest signature against the Firmware Signing Key (or a certificate chain) published in the Manifest Registry / Root Key Registry (see ADR-0007).
   - The device validates:
     - `compatible_models` (the device must be explicitly supported),
     - `min_attestation_policy` (the device must be able to satisfy the defined tests/policy).

3. **Firmware download**
   - The device downloads the firmware image using a secure transport channel (e.g., HTTPS with TLS 1.3).
   - The image is stored in a **staging** or **inactive** bank/partition, separate from the currently active firmware.

4. **Image integrity and signature checks**
   - The device computes `SHA-256(image)` and compares it to `image_hash` from the manifest.
   - The device verifies the signature:
     - either directly over the image, or
     - over the canonical manifest that binds the image hash,
     depending on how signing is configured.
   - If any verification step fails, the update is rejected and the device reports the failure (when possible).

5. **Atomic install and boot selection**
   - The new image is marked as **pending**:
     - for A/B or dual‑bank setups: the bootloader is instructed to boot from the new bank on the next restart,
     - for single‑bank + verified‑boot setups: the bootloader tracks a *pending* state and ensures a fallback path is available.
   - On the next reboot, the bootloader attempts to boot the pending image.

6. **Smoke tests and probation window**
   - After booting the new firmware, the device runs smoke tests as defined by `min_attestation_policy`, for example:
     - basic hardware checks and resource initialization,
     - connectivity checks,
     - generation and/or verification of an attestation statement,
     - limited functional tests critical for safe operation.
   - During a **probation window** (e.g., the first N boots or T minutes of operation):
     - if tests pass, the firmware is promoted from *pending* to *active*,
     - if tests fail or the device becomes unstable, the bootloader or firmware triggers rollback.

7. **Rollback and reporting**
   - On repeated failures or inability to complete smoke tests within the probation window:
     - the device reverts to the previous known‑good image,
     - the failed image is marked as invalid for further automatic retries,
     - a failure report is sent to the platform (registry/update service) when network connectivity is available.
   - On success:
     - the device marks the new firmware as *active*,
     - an update report (including version and optionally attestation data) is sent to the platform.

### Firmware signing

- Firmware images MUST be signed by a dedicated Firmware Signing Key that is kept in a secure environment (e.g., offline or hardware security module).
- The manifest MUST include:
  - `image_hash` (SHA‑256),
  - `firmware_version`,
  - `compatible_models`,
  - `min_attestation_policy`,
  - `firmware_signature`,
  - and the identity of the signing entity.
- The public part of the Firmware Signing Key (or chain of certificates) MUST be published via the Manifest Registry / Root Key Registry (ADR-0007), so that devices and back‑end services can verify signatures.
- The CI pipeline MUST:
  - build firmware artifacts,
  - generate a manifest,
  - sign the firmware or manifest,
  - publish the signed manifest to the registry as an atomic step.

### Anti-rollback and rollback handling

- **Preferred anti‑rollback mechanisms** (in order of strength):
  1. Monotonic counters or secure version fields backed by a secure element.
  2. One‑time‑programmable hardware fuses (where available).
  3. Software monotonic counters with tamper detection and attestation (least secure, but sometimes the only option).

- Devices SHOULD:
  - track the current firmware version and the minimum allowed version,
  - refuse to install firmware that violates anti‑rollback policies,
  - expose their version state via attestation or similar mechanisms when requested.

- **Rollback strategy**:
  - If smoke tests fail within the verification window (e.g., first few boots or some time‑based threshold after the update):
    - the device automatically reverts to the last known‑good image,
    - a failure report is generated and, when possible, sent to the registry/update service.

- **Safe-update window & probation**:
  - New firmware is considered *provisionally active* until the device has successfully passed the configured smoke tests and sent an update report.
  - After that, the firmware is marked as fully active on the device and in the registry.

### Notifications about new versions

- **Canonical source**: the Manifest Registry.  
  It stores firmware manifests and supports queries by model, version and other attributes.

- **Push notifications (optional)**:
  - A notification service can send signed notifications to devices using protocols like MQTT, WebSocket, or CoAP over TLS.
  - Push messages MUST be authenticated and SHOULD include or reference a signed manifest.

- **Pull model**:
  - Devices periodically poll registry endpoints with caching hints (e.g., `ETag`, `If-Modified-Since`) and exponential backoff.
  - Polling frequency MUST respect configurable update policies and device constraints (battery, bandwidth, etc.).

### Emergency updates

- The manifest includes an `emergency` flag plus:
  - a human‑readable description,
  - optional fields that limit the validity window or specify priority.

- Emergency manifests:
  - are distributed with higher priority by the registry and notification services,
  - SHOULD be preferred by devices over regular scheduled updates, even within a backoff window.

- Emergency updates still MUST:
  - be signed by a trusted Firmware Signing Key,
  - pass all usual validation steps (signature, compatibility, anti‑rollback).

### Audit and reporting

- All manifest publications and key changes SHOULD be logged and, where appropriate, anchored in an auditable system (e.g., append‑only logs, Merkle trees, or similar mechanisms).
- Devices SHOULD publish update reports to the platform, including:
  - current firmware version,
  - result of the last update attempt (success/failure),
  - reason for failure if known (e.g., signature invalid, hash mismatch, insufficient resources),
  - optional attestation data to prove device state.

- Aggregated reports can be periodically anchored or exported to external audit systems for long‑term traceability.

## Rationale

- **Separate manifest signing**:
  - Signing a small manifest document instead of the full image reduces the size of signed payloads and can simplify verification on constrained devices.
  - The manifest can bind multiple attributes (hash, version, compatibility, policies) into a single signed object.

- **Dual‑bank / verified‑boot with smoke tests**:
  - Greatly reduces the risk of bricking devices.
  - Enables automatic rollback if the new firmware fails quickly or does not meet health criteria.

- **Secure elements and hardware features**:
  - Hardware secure elements provide strong protection for keys and support reliable anti‑rollback primitives (e.g., monotonic counters).
  - Where such hardware is unavailable, software‑only mechanisms can still provide best‑effort protection, but must be treated as weaker.

- **Auditability and anchoring**:
  - Keeping a verifiable history of firmware releases and update events supports:
    - incident response,
    - regulatory and security audits,
    - forensic analysis.

## Consequences

- **Infrastructure requirements**
  - A Manifest Registry is required to store manifests and provide query APIs.
  - A storage and delivery service for firmware images is needed (e.g., object storage + CDN).
  - Optional notification services are needed for push‑style update announcements.

- **Device capabilities**
  - Devices need sufficient storage to hold at least one additional firmware image (for staging/A/B).
  - Bootloaders must support:
    - verification of firmware integrity and authenticity,
    - selection between multiple images (active vs. pending),
    - rollback logic.

- **Heterogeneous security levels**
  - Devices without secure elements or hardware anti‑rollback mechanisms:
    - face a higher risk of downgrade and key compromise,
    - may require stricter operational policies or be placed in separate risk categories.

- **Operational costs**
  - Managing signing keys, manifests, and emergency updates introduces additional operational overhead.
  - Enhanced audit and reporting capabilities incur storage and processing costs.

## Acceptance criteria (MUST)

1. ADR‑0008 is added to the architecture documentation and approved as Draft.
2. The build/CI pipeline includes:
   - firmware build steps,
   - a signing step that produces a signed manifest (and optionally a signed image),
   - publication of the manifest to the Manifest Registry as an atomic operation.
3. Reference firmware (in `firmware/`):
   - retrieves and verifies the manifest,
   - validates signatures and hashes,
   - performs atomic installation (A/B or pending),
   - runs smoke tests according to policy,
   - supports rollback,
   - reports update results.
4. End‑to‑end test:
   - an emulator or real device completes a full update cycle:
     - manifest discovery → download → validate → activate → attest (if applicable) → report to registry/service.
5. Emergency update exercise:
   - publish an emergency manifest,
   - distribute it via the configured mechanisms,
   - ensure that devices accept the emergency update (subject to the same validation rules) and report results.

## Open questions

- **Transport selection for push notifications**:
  - Which protocol(s) (MQTT, CoAP, WebSocket, others) should be supported by default?
  - How should this choice vary by device capabilities and network environment?

- **Default probation policy**:
  - What should be the default thresholds (e.g., number of successful boots, time window) before marking firmware as fully active?
  - Should there be per‑model or per‑fleet overrides?

- **Manifest schema extensions**:
  - Which optional fields are needed for real deployments (e.g., region constraints, hardware revisions, feature flags)?

## Implementation tasks

- `tools/firmware/sign`:
  - implement signing tooling and integrate it with CI/CD.
- `firmware/ota` client:
  - implement OTA client logic (download, verify, install, rollback),
  - implement dual‑bank or pending‑boot strategy,
  - integrate with secure elements where available.
- Manifest Registry:
  - implement endpoints for storing and querying firmware manifests,
  - provide hooks for notification services.
- E2E test harness:
  - emulator and/or hardware testbed,
  - CI job that runs an automated end‑to‑end OTA scenario.

---

Appendix: Minimal Firmware Manifest (example)

```json
{
  "firmware_version": "2026.07.20",
  "image_hash": "sha256:abcd...",
  "image_size": 234567,
  "compatible_models": ["generic-mcu-v1"],
  "min_attestation_policy": "policy-v1",
  "firmware_signature": "BASE64_ED25519_SIG",
  "emergency": false
}
