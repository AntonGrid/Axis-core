# Changelog

All notable changes to Axis Core will be documented in this file.

The format follows the principles of Keep a Changelog.

---

## [Unreleased]

### Added

- **AI signal layer (Phase 1, ENRG-AI)** — `axis_core.ai`: anomaly detection
  over device history (energy/power spikes vs. median, nonce jumps) and a
  dependency-free production forecast (least-squares trend). Signals only —
  decisions stay in the Policy Engine (`docs` rationale: ADR-0003).
- **AI anomaly policy gate** — new `PolicyRegistry` parameters
  `enforce_ai_anomaly` / `ai_anomaly_threshold` (off-chain, opt-in) and
  `PolicyEngine.evaluate_ai_anomaly` with the stable `ai_anomaly_flagged`
  reason. The oracle consults the signal only when the operator/DAO enables
  it; default behavior is unchanged.
- `SignalProvider` — single entry point that combines anomaly + forecast
  into one `Signal` (neutral no-op without history).
- Oracle now records recent attestations per device to feed the anomaly
  history (`_ai_history`).
- **Market recommender (Phase 3, step B)** — `axis_core.ai.recommend`: ranks
  `SELL / STORE / BUY / HOLD` from production forecast + storage + prices
  (pure function, confidence + rationale).
- **Trade policy gate** — `PolicyEngine.evaluate_trade` with stable reasons
  `trade_not_authorized`, `trade_volume_exceeded`, `trade_dao_gated`,
  `trade_allowed`; new `PolicyRegistry` parameters
  `enforce_trade_limits` / `trade_max_volume_wh` / `trade_requires_dao` and
  `ProducerState.trade_enabled` (off-chain, opt-in).
- **`POST /market/recommend`** — end-to-end API: Recommender → Policy Engine
  → authoritative `trade_decision`.
- **Premium SELL rule** — the Recommender sells stored energy when the price
  clears the rolling average (`sell_premium`, `min_sell_storage_ratio`); this
  closes the arbitrage loop used by the DePIN pilot.
- **Sterility gate (Statement #87, ENRG-AI)** — new `PolicyRegistry`
  parameters `enforce_sterility` / `sterility_a2_threshold` (0.1) /
  `sterility_cv_threshold` (0.005), off-chain and opt-in, and
  `PolicyEngine.evaluate_sterility` with the stable
  `synthetic_collusion_detected` reason. The oracle blocks a mint when a
  report carries a relief reading (`payload.sterility`) whose Anderson–Darling
  `A²` or `CV(relief)` falls below the policy floor; the thresholds belong to
  the policy, not to the signal, and a missing signal never blocks.
  Documented in `docs/policy-engine.md`.

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
