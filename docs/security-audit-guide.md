# External Security Audit — Engagement Guide

This guide prepares Axis Core and the ENRG reference implementation for an
**independent security audit** (Phase 4 of the Axis Core roadmap). It defines
the audit scope, the automation that already guards the code, and the
protocol-level controls an auditor should verify.

> An external audit **must** be performed by an independent organization. This
> document is the package handed to the auditor.

---

## 1. Scope

The audit covers two repositories and their artifacts:

| Repository | Role | Main artifacts |
| :--- | :--- | :--- |
| `Axis-core` | Universal reference implementation (off-chain) | `axis_core/*`, `oracle/registry/*`, schemas, Policy Engine, Trust Envelope codec, SDK |
| `ENRG` | Domain profile deployment (on-chain) | `programs/enrg-mvp/*` (Solana/Anchor), `policy.js`, `server.js`, firmware `esp32_proof_sender` |

On-chain artifacts of the current deployment:

- Program: `HkuC3FTGAf9ryPqH7fi3RbUHwP4TKFMg5WgHNWm6Vaxb` (devnet, slot
  `485888073`, extended to 10240 bytes);
- Domain profile program: `78FUdpHn7pWPjnDhA8RWCsXxZq6r4wVPtCcsEKBBvhUt`
  (`enrg-profile`);
- Verified economics: `mint_energy` 90 kWh → 0.0371001 SRC net
  (gross ≈ 0.04365 SRC), documented in `ENRG/docs/DEVNET_VERIFICATION.md`.

## 2. What is already automated

The following is **covered by CI in every push/PR** (green in all five
repositories of the ecosystem) and does not need to be re-verified from
scratch:

- Python test suite (incl. Policy Engine, wire format, SDK, conformance);
- Node oracle suites, including spawn-based suites (signed manifest, OTA,
  key rotation) against a live `server.js`;
- Rust host-side unit tests (`cargo test -p enrg-mvp`);
- **Anchor on-chain tests** — `anchor test` with a local validator
  (lifecycle, governance, vesting, Merkle proofs, trust/ERS pool, E2E smoke);
- Foundry tests for the on-chain governance/verification contracts;
- `npm audit` (non-blocking, reported);
- JSON Schema conformance (canonical ↔ runtime, OpenAPI ↔ routes).

## 3. Controls to verify (protocol constitution)

An auditor should confirm that the implementation honors the ADRs:

| Control | Where to look |
| :--- | :--- |
| **ADR-0001** — private key never leaves the device | No private key material in `Axis-core`; firmware signs locally; SDK signs locally (`axis_core/sdk`) |
| **ADR-0002** — Device Registry is the source of truth | `EnergyProducer` PDA on-chain; registry service off-chain |
| **ADR-0003** — Verifier executes, Policy Engine decides | On-chain `policy_engine.rs`; off-chain `axis_core/policy` (mirror tests) |
| **ADR-0005** — device lifecycle | `device_lifecycle.rs`, `can_mint` gating |
| **ADR-0009** — governance | `governance.rs`, timelock before `governance_mint` |
| Wire format §8 — envelope validation | `axis_core/wire` (`validate_envelope`, whole-envelope signature) |

## 4. Known risk areas (recommended audit focus)

These are the areas the internal audit (2026-08-20) flagged as *remaining* or
*partially covered*:

- **P1-5…P1-8** — policy/security hardening items of the internal audit
  (see `AUDIT-FINAL-2026-08-20.md` in the workspace root);
- **Multisig / timelock for privileged roles** — `set_policy_authority` and
  governance roles are single-signer in the MVP; recommend multisig before
  mainnet;
- **COSE/CBOR attestation format** — the ESP32 firmware uses a compact JSON
  payload; COSE_Sign1 / CBOR envelope is a future hardening step;
- **Binary wire-format codec** — `axis_core.wire` is JSON-based; the binary
  codec (`u8/u16/u32` big-endian) from `wire-format.md` is not implemented;
- **`better-sqlite3` native binding** — rebuild needed on Node upgrades
  (CI does `npm rebuild better-sqlite3`);
- **Oracle key management** — `ORACLE_SECRET_KEY` via environment; hardware
  key management / KMS is a mainnet requirement;
- **RPC endpoint trust** — `server.js` reads `RPC_ENDPOINT`; on-chain state
  should be cross-checked against the oracle decisions.

## 5. Deliverables expected from the auditor

1. Threat model covering the device → oracle → on-chain path;
2. Static analysis report (Rust `cargo audit`/Clippy, Python, Node);
3. Manual code review findings with severity ratings;
4. On-chain instruction-level review (`mint_energy`, `policy_engine`,
   `device_lifecycle`, `governance`, `vesting`, `merkle_proof_verification`);
5. A signed statement on ADR conformance (or deviations found);
6. Re-test of the CI pipeline as the baseline.

## 6. How to run everything for the auditor

```bash
# Axis-core
cd Axis-core && ./run-tests.sh

# ENRG — python + node + rust + anchor (spawns a local validator)
cd ENRG
pytest -q -p no:anchorpy
npm ci && npm rebuild better-sqlite3
npm run test:policy && npm run test:mint && npm run test:manifest \
  && npm run test:firmware && npm run test:keyrotation
cargo test -p enrg-mvp
anchor test

# ENRG — governance contracts (Foundry)
cd ENRG/onchain && forge test
```
