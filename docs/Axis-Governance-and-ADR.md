# Axis Governance and ADR/RFC Process (Draft)

This document describes how changes to Axis Core and Domain Modules are proposed, discussed, and accepted.

---

## 1. Scope

Axis distinguishes between:

- **Axis Core** – protocol-wide concepts, terminology, schemas, registries, and reference implementations.
- **Domain Modules** – domain-specific extensions built on top of Axis Core (e.g. ENRG Energy Domain).

Governance MUST clearly separate:

- changes that affect **Axis Core**,
- changes that affect only a specific **Domain Module**.

---

## 2. Design Records: ADR and RFC

Axis uses two complementary document types:

- **ADR (Architecture Decision Record)** – a focused document capturing a specific architecture decision.
- **RFC (Request for Comments)** – a broader proposal that may include multiple decisions, discussion, and migration paths.

Conventions:

- ADRs are stored under `adr/` in this repository (Axis Core ADRs).
- Domain Modules maintain their own ADR/RFC documents in their repositories.
- Each ADR:
  - has a unique ID (e.g. `ADR-0009`),
  - has a status (`Proposed`, `Accepted`, `Rejected`, `Superseded`),
  - references related ADRs/RFCs and implementation artifacts.

---

## 3. Axis Core Governance

Axis Core Governance is responsible for:

- Core terminology and concepts.
- Core schemas and registries (Manifest, Capability, Event, Error).
- On-chain attestation format and verification rules.
- Core conformance definitions and testing strategy.
- Protocol-level security and upgrade strategy.

Changes to Axis Core MUST:

1. Be described in an ADR or RFC.
2. Be discussed and reviewed according to the governance process (e.g. maintainers, working group, or DAO).
3. Include a migration and compatibility section, when applicable.
4. Be traceable to implementation changes (commits, releases).

Axis Core MAY define additional process details (e.g. voting, quorum) in a future governance document or smart-contract-based governance.

---

## 4. Domain Governance

Each Domain Module (e.g. ENRG Energy Domain) maintains its own governance, which is:

- responsible for domain-specific registries, events, and flows,
- responsible for domain-specific conformance rules,
- aligned with Axis Core Governance for any protocol-level impact.

Domain Governance MUST:

- document its own ADR/RFC process,
- clearly reference Axis Core ADRs it depends on or extends,
- avoid redefining Axis Core terminology and semantics.

If a domain proposal requires changes to Axis Core, it MUST:

- create or reference an Axis Core ADR/RFC,
- follow the Axis Core Governance process for that part of the change.

---

## 5. Change Types and Required Process

Examples of **Core-level changes** (require Axis Core ADR/RFC):

- Adding or changing fields in core attestation format.
- Modifying core registry schemas or semantics.
- Introducing new core actors or identity models.
- Changing conformance levels or definitions.

Examples of **Domain-level changes** (handled by Domain Governance, with reference to Core):

- Adding new domain-specific event types.
- Adding domain-specific error codes or capability types.
- Changing domain-specific token economics or flows (if applicable).
- Defining additional domain conformance checks.

When in doubt, changes SHOULD be treated as Core-level and reviewed by Axis Core Governance.

---

## 6. Versioning and Compatibility

Axis maintains explicit versions for:

- **Axis Core** (e.g. `core v8.0`),
- each **Domain Module** (e.g. `enrg-energy v1.0`).

Rules:

- Domain Module versions MUST declare which Axis Core version(s) they are compatible with.
- Breaking changes to Axis Core MUST be documented in ADRs/RFCs with:
  - impact analysis,
  - migration strategy,
  - deprecation timelines, if applicable.

---

## 7. Implementation Traceability

Every significant implementation change related to Axis Core SHOULD:

- reference one or more ADRs/RFCs in commit messages or pull requests,
- update relevant documentation and schemas,
- update tests and conformance checks.

This allows implementers and auditors to trace:

- why a decision was made,
- where it is implemented,
- which versions are affected.

---

## 8. Future Work

This document is a draft and will be refined to include:

- concrete roles and responsibilities (maintainers, working groups, DAO),
- detailed proposal and review workflow,
- examples of ADR templates and RFC templates,
- references to on-chain governance mechanisms (if/when adopted).
