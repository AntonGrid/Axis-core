# Changelog

All notable changes to Axis Core will be documented in this file.

The format follows the principles of Keep a Changelog.

---

## [Unreleased]

### Added

- Oracle now verifies real Ed25519 device signatures (`POST /oracle/attest`).
- Canonical signed-message format and Base64 key/signature encoding
  (`axis_core.signature_utils`, documented in `docs/conformance.md`).
- New decision reasons: `device_not_registered`, `signature_invalid`,
  `unsupported_algo`, `mock_disabled`.
- Shared demo client `scripts/axis_client.py` (real device signing in demos).
- **Policy Engine (ADR-0003)** — `axis_core.policy`: a single decision point
  mirroring the on-chain `PolicyEngine` of the ENRG reference implementation
  (mint pause, oracle whitelist, device-state gating, freshness, tier limits,
  energy caps, supply cap). The oracle decision pipeline is now split between
  the Verifier (cryptography) and the Policy Engine. See
  `docs/policy-engine.md`.
- **Trust Envelope wire format** — `axis_core.wire`: deterministic, versioned,
  self-describing envelopes signed as a whole (`spec/protocol/wire-format.md`).
  Proof / Attestation / Claim payloads and structural validation included.
- **SDK** — `axis_core.sdk` + `sdk/README.md`: a thin client for the reference
  HTTP API (register with proof-of-possession, submit proofs, read
  attestations) with Trust Envelope support and an injectable transport.
- Tests: `tests/test_policy_engine.py` (mirrors the on-chain unit tests),
  `tests/test_wire.py`, `tests/test_sdk_client.py`.

### Changed

- License metadata aligned with the repository `LICENSE` file: SPDX
  `Apache-2.0` (was `MIT`).
- Author metadata corrected to Anton Gulda.
- `algo = "mock"` is now a dev-only mode (requires `AXIS_ALLOW_MOCK`); the
  oracle requires `ed25519` signatures by default.
- Orphaned Rust tests moved to the ENRG `enrg-mvp` crate (where they belong).
- `docs/conformance.md`: the wire-format gap is closed (JSON Trust Envelope
  codec); ADR-0003 Policy Engine split documented.

---

## [1.0.0] - Unreleased

### Added

- Axis Architecture Book
- Architecture Decision Records
- Device Lifecycle Specification
- Provisioning Specification
- Protocol Specification
- Technical Documentation v1.0
- Project Roadmap
- Security Policy
- Contributing Guide

### Changed

- Axis Core redefined as a universal reference implementation of Axis Protocol.
- Repository reorganized.
- Documentation restructured.
- Architecture-first development process adopted.

### Planned

- Device Registry
- Policy Engine
- Provisioning Service
- Dashboard
- Oracle Network
- SDK
- Mainnet preparation

---

## Previous Versions

See Git history for changes before version 1.0.
