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

### Changed

- License metadata aligned with the repository `LICENSE` file: SPDX
  `Apache-2.0` (was `MIT`).
- Author metadata corrected to Anton Gulda.
- `algo = "mock"` is now a dev-only mode (requires `AXIS_ALLOW_MOCK`); the
  oracle requires `ed25519` signatures by default.
- Orphaned Rust tests moved to the ENRG `enrg-mvp` crate (where they belong).

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
