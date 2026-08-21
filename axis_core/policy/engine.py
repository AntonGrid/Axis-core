"""Policy Engine (ADR-0003) — the single decision point.

Behavior mirrors the on-chain ``PolicyEngine`` of the ENRG reference
implementation (``programs/enrg-mvp/src/instructions/policy_engine.rs``):

- ``evaluate_preamble`` — the "predicate" part: mint pause, oracle whitelist,
  device state (ADR-0005), ``verified_at`` freshness, monthly tier limits
  (v7.0 §15), and the per-proof energy cap;
- ``evaluate_reward`` — the "reward" part: no zero mints and the supply cap.

The Verifier (``axis_core.api.oracle``) is an **executor**: it performs the
cryptography and calls this engine for every admissibility decision.

Reason codes are stable and backward compatible with the oracle API:

- ``mint_paused``          (on-chain ``MintPaused``)
- ``untrusted_oracle``     (``UntrustedOracle``)
- ``invalid_device_state`` (``InvalidDeviceState``)
- ``future_timestamp``     (``FutureTimestamp``)
- ``stale_timestamp``      (``StaleProof``)
- ``tier_limit_exceeded``  (``TierLimitExceeded``)
- ``excessive_energy``     (``ExcessiveEnergy``)
- ``zero_amount_mint``     (``ZeroAmountMint``)
- ``supply_limit_exceeded`` (``SupplyLimitExceeded``)
"""
from __future__ import annotations

from typing import Any, Optional

from axis_core.policy.models import OracleReport, PolicyDecision, PolicyRegistry, ProducerState

#: Mirrors on-chain ``constants.rs``: DEFAULT_MAX_ENERGY_BPS = 10_000,
#: MAX_CLOCK_SKEW = 300, MAX_PROOF_AGE = 900 (security/validation.rs).
DEFAULT_MAX_ENERGY_BPS = 10_000
DEFAULT_MAX_CLOCK_SKEW_SEC = 300
DEFAULT_MAX_PROOF_AGE_SEC = 900


class PolicyError(Exception):
    """Raised by callers that prefer exceptions over decision objects.

    ``reason`` carries the same stable reason code used in ``PolicyDecision``.
    """

    def __init__(self, reason: str, **details: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


class PolicyEngine:
    """Pure decision functions with the on-chain parameter semantics.

    Every method is a pure function: given the policy set (``None`` → protocol
    defaults) and the current inputs it returns a ``PolicyDecision``. No state
    is stored here — replay state, registry lookups and signatures belong to
    the Verifier, matching the on-chain split (``mint.rs`` verifies nonce,
    ``policy_engine.rs`` decides).
    """

    # ── Predicate part (mirrors on-chain evaluate_preamble) ──────────────────

    @staticmethod
    def evaluate_preamble(
        *,
        policy: Optional[PolicyRegistry],
        producer: ProducerState,
        report: OracleReport,
        now: int,
        oracle_trusted: bool = True,
        max_energy_bps: Optional[int] = None,
    ) -> PolicyDecision:
        """Decide whether a report is admissible *before* any reward is computed.

        Parameters (all defaulted from the policy set or the protocol defaults,
        exactly as on-chain ``MintPreambleInput``):

        - ``policy`` — policy snapshot; ``None`` → protocol defaults.
        - ``producer`` — the device state from the Device Registry.
        - ``report`` — the oracle report under evaluation.
        - ``now`` — current Unix time (sec).
        - ``oracle_trusted`` — C-0: whether the report oracle is whitelisted.
        - ``max_energy_bps`` — optional override for the energy cap basis points.
        """
        p = policy
        mint_enabled = p.mint_enabled if p else True
        enforce_whitelist = p.enforce_oracle_whitelist if p else True
        enforce_state = p.enforce_device_state if p else True
        enforce_tier = p.enforce_tier_limits if p else True
        enforce_energy = p.enforce_energy_caps if p else True
        bps = (
            max_energy_bps
            if max_energy_bps is not None
            else (p.max_energy_bps if p else DEFAULT_MAX_ENERGY_BPS)
        )
        skew = p.max_clock_skew_sec if p else DEFAULT_MAX_CLOCK_SKEW_SEC

        # 0. Global switch (maintenance / pause).
        if not mint_enabled:
            return PolicyDecision(allowed=False, reason="mint_paused")

        # 1. C-0: the report must come from a trusted oracle.
        if enforce_whitelist and not oracle_trusted:
            return PolicyDecision(allowed=False, reason="untrusted_oracle")

        # 2. Device state (ADR-0005): only Active devices may mint.
        if enforce_state and not producer.can_mint(now):
            return PolicyDecision(allowed=False, reason="invalid_device_state")

        # 3. verified_at freshness (the policy sets the allowed clock skew).
        if report.verified_at > now + skew:
            return PolicyDecision(allowed=False, reason="future_timestamp")
        if now - report.verified_at > DEFAULT_MAX_PROOF_AGE_SEC:
            return PolicyDecision(allowed=False, reason="stale_timestamp")

        # 4. Monthly tier limit (v7.0 §15).
        if enforce_tier and not producer.tier.allows_increment(
            producer.effective_month_energy(now), report.energy_wh
        ):
            return PolicyDecision(allowed=False, reason="tier_limit_exceeded")

        # 5. Energy per proof <= rated_power * max_energy_bps / 10_000.
        if enforce_energy:
            max_energy = (producer.rated_power_wh * bps) // 10_000
            if report.energy_wh > max_energy:
                return PolicyDecision(
                    allowed=False,
                    reason="excessive_energy",
                    details={
                        "max_energy_wh": max_energy,
                        "rated_power_wh": producer.rated_power_wh,
                        "max_energy_bps": bps,
                    },
                )

        return PolicyDecision.allowed_ok()

    # ── Reward part (mirrors on-chain evaluate_reward) ───────────────────────

    @staticmethod
    def evaluate_reward(
        *,
        policy: Optional[PolicyRegistry],
        reward: int,
        vault_total_supply: int,
        vault_max_supply: int,
    ) -> PolicyDecision:
        """Decide whether a computed reward may be minted.

        - ``reward`` must be positive (no "empty" mints — always enforced);
        - if ``enforce_supply_cap`` is enabled, ``total_supply + reward`` must
          not exceed ``vault_max_supply``.
        """
        enforce_supply = policy.enforce_supply_cap if policy else True

        if reward <= 0:
            return PolicyDecision(allowed=False, reason="zero_amount_mint")

        if enforce_supply and vault_total_supply + reward > vault_max_supply:
            return PolicyDecision(allowed=False, reason="supply_limit_exceeded")

        return PolicyDecision.allowed_ok()
