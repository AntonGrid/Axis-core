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
- ``ai_anomaly_flagged``   (off-chain, Phase 1 — ENRG-AI opt-in gate; the
  on-chain verifier does not know about it, by design)
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

        # 3b. device_timestamp freshness (audit 2026-09-16) — mirrors the on-chain
        # check added to `policy_engine.rs`. `verified_at` is the oracle's clock,
        # `device_timestamp` is the device's own clock; the latter used to be bound
        # only by the device signature and never range-checked, so a device could
        # anchor a proof to an arbitrary time. The live pilot's delta is 1..3 s.
        if report.device_timestamp > now + skew:
            return PolicyDecision(allowed=False, reason="future_timestamp")
        if now - report.device_timestamp > DEFAULT_MAX_PROOF_AGE_SEC:
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

    # ── AI signals (Phase 1, ENRG-AI): off-chain extension ───────────────────

    @staticmethod
    def evaluate_ai_anomaly(
        *,
        policy: Optional[PolicyRegistry],
        signal: Any,
        threshold: Optional[float] = None,
    ) -> PolicyDecision:
        """Decide whether an AI anomaly signal rejects the report.

        This is an **off-chain, opt-in** gate (``enforce_ai_anomaly``):
        disabled by default so behavior is unchanged until an operator/DAO
        turns it on. It is NOT mirrored on-chain — it is an additional,
        verifiable layer on top of the protocol rules.

        ``signal`` only needs ``is_anomaly`` and ``score`` (duck typing, so
        the engine does not depend on the AI package): any object with the
        same shape works. Reason code ``ai_anomaly_flagged`` is stable.

        Returns:
            ``allowed=False`` with ``reason="ai_anomaly_flagged"`` only when
            the policy opted in, the signal says ``anomaly``, and the score
            clears ``threshold`` (default: ``policy.ai_anomaly_threshold``).
        """
        enforce = policy.enforce_ai_anomaly if policy else False
        thr = (
            threshold
            if threshold is not None
            else (policy.ai_anomaly_threshold if policy else 0.6)
        )

        if not enforce:
            return PolicyDecision.allowed_ok()

        if getattr(signal, "is_anomaly", False) and signal.score >= thr:
            return PolicyDecision(
                allowed=False,
                reason="ai_anomaly_flagged",
                details={
                    "ai_score": signal.score,
                    "ai_signals": getattr(signal, "details", {}).get("signals", []),
                },
            )

        return PolicyDecision.allowed_ok()

    # ── Market gate (Phase 3, ENRG-AI): recommendation → authorized action ──

    @staticmethod
    def evaluate_trade(
        *,
        policy: Optional[PolicyRegistry],
        recommendation: Any,
        producer: ProducerState,
        dao_approved: bool = False,
        volume_wh: Optional[float] = None,
    ) -> PolicyDecision:
        """Decide whether a market recommendation may be executed.

        This is the **off-chain, opt-in** market gate: the Recommender ranks
        actions, but only a device with the trading right, within volume
        limits and past any DAO gate may act. ``recommendation`` only needs
        ``action`` and ``volume_wh`` (duck typing).

        Reason codes (stable):
        - ``trade_not_authorized`` — device has no trading right;
        - ``trade_volume_exceeded`` — volume above ``trade_max_volume_wh``;
        - ``trade_dao_gated``      — DAO approval required but not given;
        - ``trade_allowed``        — the action may proceed.
        """
        # 1. The device must have the trading right.
        if not producer.trade_enabled:
            return PolicyDecision(allowed=False, reason="trade_not_authorized")

        volume = volume_wh if volume_wh is not None else float(getattr(recommendation, "volume_wh", 0.0))
        if volume < 0:
            volume = 0.0

        # 2. Volume limits.
        if (
            policy is not None
            and policy.enforce_trade_limits
            and policy.trade_max_volume_wh > 0
            and volume > policy.trade_max_volume_wh
        ):
            return PolicyDecision(
                allowed=False,
                reason="trade_volume_exceeded",
                details={
                    "volume_wh": round(volume, 2),
                    "trade_max_volume_wh": policy.trade_max_volume_wh,
                },
            )

        # 3. DAO gate.
        if policy is not None and policy.trade_requires_dao and not dao_approved:
            return PolicyDecision(allowed=False, reason="trade_dao_gated")

        return PolicyDecision(
            allowed=True,
            reason="trade_allowed",
            details={"action": getattr(recommendation, "action", "HOLD"), "volume_wh": round(volume, 2)},
        )
