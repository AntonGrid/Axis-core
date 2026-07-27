# Axis Protocol – One Pager (Draft)

## What is Axis?

Axis Protocol is a domain-agnostic trust and attestation framework that connects physical devices and digital systems.

Axis defines:
- how devices and actors are identified,
- how claims about them are issued and verified on-chain,
- how registries of manifests, capabilities, events and errors are maintained,
- how governance and policy are enforced across domains.

Energy, mobility, IoT, or any other vertical can implement a **Domain Module** on top of Axis Core.

---

## Core Building Blocks

- **Identity & Actors**
  - Model for devices, organizations, and services.
  - Links between off-chain identifiers and on-chain accounts.

- **On-chain Attestation**
  - Standard format for claims about devices and events.
  - Contracts/programs to issue, verify, and revoke attestations.

- **Registries**
  - **Manifest Registry** – what this device/actor is.
  - **Capability Registry** – what this device/actor can do.
  - **Event Registry** – what happened and when.
  - **Error Registry** – standardized failure and error codes.

- **Policy & Governance**
  - Rules for who can issue which attestations.
  - Upgrade and change management via ADR/RFC process.
  - Conformance requirements for implementations and domains.

---

## Axis Core vs Domain Modules

- **Axis Core**
  - Domain-agnostic specifications and reference implementation.
  - Defines common terminology, schemas, and governance.
  - Owns the ADR/RFC process for protocol-level changes.

- **Domain Modules (e.g. ENRG Energy Domain)**
  - Extend Axis with domain-specific registries and flows.
  - Reuse Axis Core primitives for identity and attestation.
  - Must comply with Axis Core conformance and governance.

---

## Current Status

Axis Core is being extracted from an energy-focused prototype (ENRG) into a clean, domain-agnostic protocol.

Short-term goals:
- Stabilize Axis terminology, architecture, and registries.
- Separate ENRG Energy Domain into its own repository.
- Define clear conformance criteria for Axis Core and domains.
