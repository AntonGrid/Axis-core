# Device Lifecycle Specification

**Status:** Draft v0.1

## Introduction

This document describes the complete lifecycle of a device within the Axis
Protocol ecosystem. All devices go through a sequence of states, each of which
defines their behavior, rights, and available actions.

The goal is to ensure **transparency, manageability, and security** of the
trust pipeline.

This specification is **implementation-oriented**: it complements the normative
lifecycle defined in the Axis Protocol (`docs/platform/device-lifecycle.md` in the
Axis-protocol repository) and in ADR-0005.

---

## Device States

### 1. UNREGISTERED

The device is unknown to the system. It has no cryptographic identity within Axis.

**Actions:**
- Generate a cryptographic key pair (private/public key).
- Send a registration request with the public key.

### 2. REGISTERED

The device has a cryptographic identity but is not yet linked to an owner.

**Actions:**
- Wait for owner linking via Claim Code.
- Send heartbeat (periodic status signals).

### 3. CLAIMED

The device is linked to a specific owner but not yet configured for operation.

**Actions:**
- Receive configuration (Device Manifest).
- Configure network, synchronize time.

### 4. PROVISIONED

The device is fully configured and ready for operation, but not yet active.

**Actions:**
- Wait for an activation command.
- Perform a self-test of all systems.

### 5. ACTIVE

The device is fully operational, signing and sending Proofs to a Verifier.

**Actions:**
- Generate and send Proofs of physical events.
- Send heartbeat signals.
- Respond to verification requests.

Domain profiles MAY add further actions here (for example, participation in
protocol pools or accumulation of domain-specific tokens).

### 6. QUARANTINE

The device is suspected of malfunction or compromise. Its data is not processed
for minting or rewards, but diagnostics remain available.

**Possible causes:**
- Suspicious activity (anomalous power, frequent errors).
- Missed heartbeats.
- Reports from other network participants.

**Actions:**
- Send diagnostic data.
- Manual or automated analysis.
- Return to ACTIVE after the issue is resolved.

### 7. MAINTENANCE

The device is temporarily taken out of operation for maintenance (sensor
replacement, software update).

**Actions:**
- Stop producing Proofs.
- After completion — return to ACTIVE.

### 8. REVOKED

The device is permanently decommissioned.

**Possible causes:**
- Key compromise.
- Sale or transfer to a new owner (through the official mechanism).
- Violation of network rules.

**Actions:**
- All further actions are blocked.
- Removal from the registry.
- Data cleanup (if required).

---

## State Transitions

```text
UNREGISTERED
    │
    ▼ (registration)
REGISTERED
    │
    ▼ (owner linking via Claim Code)
CLAIMED
    │
    ▼ (configuration)
PROVISIONED
    │
    ▼ (activation)
ACTIVE
    │
    ├── (suspicion/failure) → QUARANTINE → (recovery) → ACTIVE
    │
    ├── (maintenance) → MAINTENANCE → (completion) → ACTIVE
    │
    └── (revocation/transfer) → REVOKED
```

| From | To | Trigger |
| :--- | :--- | :--- |
| UNREGISTERED | REGISTERED | Registration request with valid public key |
| REGISTERED | CLAIMED | Claim Code entered by the owner |
| CLAIMED | PROVISIONED | Device configured and self-test passed |
| PROVISIONED | ACTIVE | Activation command from owner or system |
| ACTIVE | QUARANTINE | Suspicious activity, policy violation |
| ACTIVE | MAINTENANCE | Scheduled or unscheduled maintenance |
| ACTIVE | REVOKED | Owner or system revocation |
| QUARANTINE | ACTIVE | Diagnostics passed, issue resolved |
| QUARANTINE | REVOKED | Issue cannot be resolved or device compromised |
| QUARANTINE | MAINTENANCE | Maintenance required |
| MAINTENANCE | ACTIVE | Maintenance complete |
| MAINTENANCE | REVOKED | Device cannot be restored |
| REVOKED | (terminal) | No transitions out |

---

## Normative Requirements

- **State Authority:** The Device Registry is the single source of truth for device state.
- **State Changes:** All state transitions MUST be authorized and logged.
- **Auditability:** State transitions MUST be auditable for compliance and security review.
- **Trust Preservation:** State transitions MUST preserve the chain of trust.

---

## Related Documents

- ADR-0002: Device Registry as the Single Source of Truth
- ADR-0005: Device States and Lifecycle
- [Provisioning Specification](./provisioning.md)
