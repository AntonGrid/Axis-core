# Policy Engine (ADR-0003)

The **Policy Engine** is the single decision point for Proof admissibility.
Per ADR-0003 the Verifier is an **executor**, not a source of policies:

- the **Verifier** (`axis_core.api.oracle`) performs the cryptography and data
  transport: algorithm support, device registration lookup, Ed25519 signature
  verification, nonce replay protection;
- the **Policy Engine** (`axis_core.policy`) makes every admissibility
  decision: mint pause, oracle whitelist, device-state gating (ADR-0005),
  timestamp freshness, monthly tier limits (v7.0 §15), per-proof energy caps
  and the reward supply cap.

## On-chain parity

The decision semantics mirror the **on-chain PolicyEngine** of the ENRG
reference implementation:

| Decision | On-chain (ENRG) | Off-chain (`axis_core.policy`) |
| :--- | :--- | :--- |
| mint pause | `policy_engine.rs` → `MintPaused` | `mint_paused` |
| oracle whitelist (C-0) | `UntrustedOracle` | `untrusted_oracle` |
| device state (ADR-0005) | `InvalidDeviceState` | `invalid_device_state` |
| future timestamp | `FutureTimestamp` | `future_timestamp` |
| stale proof | `StaleProof` | `stale_timestamp` |
| monthly tier limit | `TierLimitExceeded` | `tier_limit_exceeded` |
| energy per proof | `ExcessiveEnergy` | `excessive_energy` |
| zero reward | `ZeroAmountMint` | `zero_amount_mint` |
| supply cap | `SupplyLimitExceeded` | `supply_limit_exceeded` |

The models (`DeviceState`, `DeviceTier`, `PolicyRegistry`, `OracleReport`,
`ProducerState`) and the constants (100 kWh / 10 MWh tier limits,
`max_energy_bps = 10_000`, `max_clock_skew = 300 s`, `MAX_PROOF_AGE = 900 s`)
are kept in lock-step with `programs/enrg-mvp/src/` of the ENRG repository.
`tests/test_policy_engine.py` mirrors the on-chain unit tests so both sides
are provably in agreement.

## Configuration

Policy parameters are **not hardcoded** (ADR-0003). The reference service
loads them with the same precedence as the ENRG oracle (`policy.js`):

```
environment variables (AXIS_POLICY_*) > policy config file > defaults
```

| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `AXIS_POLICY_MINT_ENABLED` | `true` | Global mint switch |
| `AXIS_POLICY_ENFORCE_ORACLE_WHITELIST` | `false`¹ | Oracle whitelist (C-0) |
| `AXIS_POLICY_ENFORCE_DEVICE_STATE` | `false`¹ | ADR-0005 state gating |
| `AXIS_POLICY_ENFORCE_TIER_LIMITS` | `false`¹ | Monthly tier limits |
| `AXIS_POLICY_ENFORCE_ENERGY_CAPS` | `false`¹ | Per-proof energy cap |
| `AXIS_POLICY_ENFORCE_SUPPLY_CAP` | `true` | Reward supply cap |
| `AXIS_POLICY_MAX_ENERGY_BPS` | `10000` | Energy cap in bps of rated power |
| `AXIS_POLICY_MAX_CLOCK_SKEW_SEC` | `300` | Allowed clock skew (0–3600) |
| `AXIS_POLICY_FILE` | — | Path to a JSON policy file |

¹ The reference service uses the simplified lifecycle subset of the registry
(`provisioned/active/suspended/retired`): there is no on-chain `Active` state,
no tier accounting and no rated power. The **full** on-chain defaults
(`enforce_* = True`) are enforced by the ENRG deployment profile; the engine
itself implements the complete semantics and is validated against them.

## Reason codes

Stable reason codes are backward compatible with the oracle API
(`decision.reason`): `mint_paused`, `untrusted_oracle`,
`invalid_device_state`, `future_timestamp`, `stale_timestamp`,
`tier_limit_exceeded`, `excessive_energy`, `zero_amount_mint`,
`supply_limit_exceeded`.
