# Axis Terminology (Draft)

This document defines core terminology used in the Axis Protocol.  
It is **normative** for Axis Core and **referential** for Domain Modules.

---

## 1. Axis Core

**Axis Core** is the domain-agnostic part of the Axis Protocol. It defines:

- common concepts, terminology, and schemas,
- on-chain and off-chain components for identity and attestation,
- registries (manifest, capability, event, error),
- governance (ADR/RFC process) and conformance requirements.

All Domain Modules MUST be compatible with Axis Core.

---

## 2. Domain Module

A **Domain Module** is a specialization of Axis Core for a specific vertical (e.g. energy, mobility, IoT).

Characteristics:

- Defines domain-specific registries, events, and flows.
- Reuses Axis Core primitives for identity, attestation, and governance.
- MUST NOT redefine or conflict with Axis Core terminology.
- MUST document its own conformance rules on top of Axis Core.

Example: **ENRG Energy Domain** is a Domain Module for energy generation and metering.

---

## 3. Actor

An **Actor** is any identifiable participant interacting with Axis:

- physical devices (sensors, meters, controllers),
- organizations (manufacturers, operators, auditors),
- services (oracles, applications, contracts).

Each Actor has:

- one or more **off-chain identifiers** (e.g. serial number, certificate subject, legal entity ID),
- one or more **on-chain accounts** (e.g. public keys, program IDs),
- a **Manifest** describing its identity and properties.

---

## 4. Identity

**Identity** in Axis refers to the binding between:

- an Actor,
- its off-chain identifiers,
- its on-chain accounts.

Axis does not mandate a single global identity system, but defines:

- how identity information is represented in Manifests,
- how it is referenced in Attestations and Registries.

---

## 5. Attestation

An **Attestation** is a structured claim about an Actor, asset, or event, which can be:

- issued by an authorized Actor,
- stored and verified on-chain,
- revoked or superseded.

Properties:

- Includes subject (who/what the attestation is about),
- Includes issuer (who created the attestation),
- Includes payload (the claim itself, often referencing a registry schema),
- Includes metadata (timestamps, version, domain tags, etc.).

Axis defines the **on-chain attestation format** and verification rules.  
Domain Modules may define additional payload schemas and constraints.

---

## 6. Registry

A **Registry** is a structured collection of records maintained under Axis governance.

Core registries in Axis:

- **Manifest Registry** – describes Actors (devices, organizations, services).
- **Capability Registry** – describes what Actors can do (functions, interfaces, supported features).
- **Event Registry** – describes events that can be reported/attested in the system.
- **Error Registry** – describes standardized error and failure codes.

Registries are versioned and governed:

- Axis Core owns core registries and their schemas.
- Domain Modules may define domain-specific registry extensions, referencing Axis Core.

---

## 7. Manifest

A **Manifest** is a record in the Manifest Registry that describes an Actor or asset.

Typical content:

- identity information (identifiers, keys, certificates),
- device or service type,
- manufacturer or operator,
- supported capabilities (references to Capability Registry),
- domain tags (e.g. energy, mobility).

Manifests are usually created during provisioning or onboarding.

---

## 8. Capability

A **Capability** describes a function or behavior that an Actor can perform.

Examples:

- "measure active power every 1s",
- "sign attestation with secure element",
- "serve as oracle for a specific registry",
- "submit metering data for a given domain".

Capabilities are defined in the Capability Registry.  
Domain Modules may add domain-specific capability categories while reusing the same structure.

---

## 9. Event

An **Event** describes something that has happened in the system and can be attested.

Examples:

- device booted,
- firmware updated,
- measurement sample reported,
- anomaly or fault detected.

Axis Core defines the generic event model and core event types.  
Domain Modules define domain-specific event types and payloads.

---

## 10. Error

An **Error** is a standardized representation of a failure condition.

Examples:

- invalid manifest reference,
- unauthorized issuer,
- schema validation failed,
- device communication timeout.

Errors are defined in the Error Registry and referenced by code and attestations.

---

## 11. Governance

**Governance** in Axis defines:

- who can propose and approve changes to Axis Core,
- how ADR/RFCs are created, reviewed, and accepted,
- how registries and schemas are versioned and deprecated.

Levels:

- **Axis Core Governance** – for protocol-wide changes and core registries.
- **Domain Governance** – for Domain Module–specific extensions, aligned with Axis Core rules.

Domain Governance MUST NOT bypass Axis Core governance for protocol-level changes.

---

## 12. Conformance

**Conformance** is the degree to which an implementation or Domain Module follows Axis specifications.

Axis defines:

- **Core Conformance** – minimal requirements to be considered an Axis-compatible implementation.
- **Domain Conformance** – additional requirements for a given Domain Module, building on Core Conformance.

Conformance may be checked by:

- automated tests and CI pipelines,
- audits and certification processes,
- on-chain verification rules.

Implementations and Domain Modules SHOULD document which conformance level(s) they target.
