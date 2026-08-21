# Axis Core Roadmap

## Vision

Build a **universal reference implementation** of the Axis Protocol — an open, platform-agnostic standard for cryptographically verifiable trust between physical devices and digital systems.

The long-term goal is to establish Axis Core as the foundational runtime for any domain that requires trust between physical and digital worlds.

---

## Phase 1 — Core Foundation ✅

- Universal trust model
- Device identity and registry abstractions
- Proof and attestation interfaces
- Policy Engine abstraction
- Oracle / Verifier abstraction
- Canonical wire format
- Validation pipeline
- JSON Schemas for core artifacts
- Documentation and ADRs

**Status:** Complete

---

## Phase 2 — Services & SDK 🚧

- Device Registry service ✅ (provisioning → registry reference flow)
- Provisioning service ✅ (register + attest reference flow)
- Policy Engine implementation ✅ (`axis_core.policy`, ADR-0003 — mirrors the
  on-chain `PolicyEngine`; see `docs/policy-engine.md`)
- Oracle / Verifier implementation ✅ (Ed25519 device signature verification,
  ADR-0003 split: Verifier = cryptography, Policy Engine = decisions)
- Trust Envelope wire format ✅ (`axis_core.wire` — deterministic, versioned,
  signed as a whole; `spec/protocol/wire-format.md`)
- SDK for Python ✅ (`axis_core.sdk` + `sdk/README.md`)
- SDK for TypeScript ⬜
- REST API ✅ (9 endpoints, documented in `openapi.yaml`)
- Developer documentation ✅ (API.md, SCHEMAS.md, docs/conformance.md,
  docs/policy-engine.md)

**Status:** In Progress

---

## Phase 3 — Ecosystem & Integrations

- CLI tools
- Reference integrations (databases, message queues, ledgers)
- Developer portal
- Community contributions
- Integration guides

---

## Phase 4 — Production Readiness

- Independent security audit 🔶 (package ready: `docs/security-audit-guide.md`;
  execution requires an external organization)
- Performance testing
- Formal verification (selected components)
- Production-ready documentation
- Release candidate

---

## Phase 5 — Universal Adoption

- Additional language SDKs (Rust, Go, Java)
- Bindings for multiple ledgers and storage backends
- Domain profiles (energy, supply chain, identity, etc.)
- Open governance
- International adoption

---

## Guiding Principle

Every release should move Axis Core closer to becoming a universal, production-ready implementation of the Axis Protocol — independent of any specific domain, blockchain, or runtime.
