"""Policy Engine tests (ADR-0003).

Mirrors the on-chain unit tests of the ENRG reference implementation
(``programs/enrg-mvp/src/instructions/policy_engine.rs``) so that the
off-chain oracle and the on-chain verifier are provably in agreement.
"""
from axis_core.policy.config import load_policy_config
from axis_core.policy.engine import DEFAULT_MAX_CLOCK_SKEW_SEC, PolicyEngine
from axis_core.policy.models import (
    DeviceState,
    DeviceTier,
    OracleReport,
    PolicyRegistry,
    ProducerState,
)


def _default_policy() -> PolicyRegistry:
    """Full on-chain defaults (``enforce_* = True``), mirroring the ENRG
    Policy Registry defaults. This is what the on-chain verifier enforces;
    the relaxed reference-service defaults live in ``policy.config``.
    """
    return PolicyRegistry()


def _active_producer(
    *,
    tier: DeviceTier = DeviceTier.INDUSTRIAL,
    month_energy_wh: int = 0,
    rated_power_wh: int = 10_000,
    state: DeviceState = DeviceState.ACTIVE,
) -> ProducerState:
    return ProducerState(
        device_id="dev_test",
        state=state,
        tier=tier,
        month_energy_wh=month_energy_wh,
        month_start_ts=1_000,
        rated_power_wh=rated_power_wh,
    )


def _report(*, energy_wh: int, verified_at: int) -> OracleReport:
    return OracleReport(
        device_id="dev_test",
        nonce=1,
        device_timestamp=verified_at,
        verified_at=verified_at,
        energy_wh=energy_wh,
    )


def _evaluate(
    *,
    policy=None,
    producer=None,
    report=None,
    now: int = 1_160,
    oracle_trusted: bool = True,
):
    return PolicyEngine.evaluate_preamble(
        policy=policy,
        producer=producer or _active_producer(),
        # Default report stays within the default energy cap (10_000 Wh for
        # rated_power 10_000 × 10_000 bps), so it only exercises the rule
        # under test.
        report=report or _report(energy_wh=5_000, verified_at=1_100),
        now=now,
        oracle_trusted=oracle_trusted,
    )


# ── Preamble: full on-chain policy (enforce_* = True) ────────────────────────


def test_default_full_policy_allows_valid_report():
    policy = PolicyRegistry()  # full on-chain defaults
    decision = _evaluate(policy=policy, now=1_160)
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_mint_paused_blocks_everything():
    policy = _default_policy()
    policy.mint_enabled = False
    decision = _evaluate(policy=policy)
    assert decision.allowed is False
    assert decision.reason == "mint_paused"


def test_whitelist_rejects_untrusted_oracle():
    policy = _default_policy()
    policy.enforce_oracle_whitelist = True
    decision = _evaluate(policy=policy, oracle_trusted=False)
    assert decision.allowed is False
    assert decision.reason == "untrusted_oracle"


def test_whitelist_relaxed_accepts_untrusted_oracle():
    policy = _default_policy()
    policy.enforce_oracle_whitelist = False
    decision = _evaluate(policy=policy, oracle_trusted=False)
    assert decision.allowed is True


def test_device_state_gating_only_active_mints():
    policy = _default_policy()
    policy.enforce_device_state = True
    for state in (
        DeviceState.UNREGISTERED,
        DeviceState.REGISTERED,
        DeviceState.CLAIMED,
        DeviceState.PROVISIONED,
        DeviceState.QUARANTINE,
        DeviceState.MAINTENANCE,
        DeviceState.REVOKED,
    ):
        decision = _evaluate(policy=policy, producer=_active_producer(state=state))
        assert decision.allowed is False, f"{state} must not mint"
        assert decision.reason == "invalid_device_state"

    decision = _evaluate(
        policy=policy, producer=_active_producer(state=DeviceState.ACTIVE)
    )
    assert decision.allowed is True


def test_device_state_gating_disabled():
    policy = _default_policy()
    policy.enforce_device_state = False
    decision = _evaluate(policy=policy, producer=_active_producer(state=DeviceState.REVOKED))
    assert decision.allowed is True


def test_future_timestamp_rejected():
    policy = _default_policy()
    policy.enforce_device_state = False
    now = 1_160
    decision = _evaluate(
        policy=policy,
        report=_report(energy_wh=50_000, verified_at=now + DEFAULT_MAX_CLOCK_SKEW_SEC + 1),
        now=now,
    )
    assert decision.allowed is False
    assert decision.reason == "future_timestamp"


def test_stale_timestamp_rejected():
    policy = _default_policy()
    policy.enforce_device_state = False
    now = 1_160
    decision = _evaluate(
        policy=policy,
        report=_report(energy_wh=50_000, verified_at=now - 901),
        now=now,
    )
    assert decision.allowed is False
    assert decision.reason == "stale_timestamp"


def test_clock_skew_is_configurable():
    policy = _default_policy()
    policy.enforce_device_state = False
    policy.max_clock_skew_sec = 3_600
    now = 1_160
    decision = _evaluate(
        policy=policy,
        report=_report(energy_wh=5_000, verified_at=now + 3_600),
        now=now,
    )
    assert decision.allowed is True

def test_tier_limit_enforced():
    policy = _default_policy()
    policy.enforce_device_state = False
    # Basic tier: 100 kWh/month. 60_000 + 50_000 > 100_000 → denied.
    decision = _evaluate(
        policy=policy,
        producer=_active_producer(tier=DeviceTier.BASIC, month_energy_wh=60_000),
        report=_report(energy_wh=50_000, verified_at=1_100),
        now=1_160,
    )
    assert decision.allowed is False
    assert decision.reason == "tier_limit_exceeded"


def test_tier_limit_disabled():
    policy = _default_policy()
    policy.enforce_device_state = False
    policy.enforce_tier_limits = False
    # rated_power raised so the energy does not hit the energy cap: we check
    # specifically the tier-limit relaxation (60_000 + 50_000 > 100_000).
    decision = _evaluate(
        policy=policy,
        producer=_active_producer(
            tier=DeviceTier.BASIC, month_energy_wh=60_000, rated_power_wh=500_000
        ),
        report=_report(energy_wh=50_000, verified_at=1_100),
        now=1_160,
    )
    assert decision.allowed is True


def test_excessive_energy_rejected():
    policy = _default_policy()
    policy.enforce_device_state = False
    # rated_power = 10_000, bps = 10_000 → max 10_000 Wh; report 11_000.
    decision = _evaluate(
        policy=policy,
        report=_report(energy_wh=11_000, verified_at=1_100),
        now=1_160,
    )
    assert decision.allowed is False
    assert decision.reason == "excessive_energy"


def test_max_energy_bps_scales_limit():
    policy = _default_policy()
    policy.enforce_device_state = False
    policy.max_energy_bps = 150_000  # 1500%
    decision = _evaluate(
        policy=policy,
        report=_report(energy_wh=100_000, verified_at=1_100),
        now=1_160,
    )
    assert decision.allowed is True


def test_none_policy_falls_back_to_protocol_defaults():
    # policy=None behaves like on-chain Option<&PolicyRegistry> → defaults,
    # with the full on-chain default set (enforce_* = True).
    decision = _evaluate(
        policy=None,
        producer=_active_producer(tier=DeviceTier.BASIC, month_energy_wh=60_000),
        report=_report(energy_wh=50_000, verified_at=1_100),
        now=1_160,
    )
    assert decision.allowed is False
    assert decision.reason == "tier_limit_exceeded"


# ── Reward part ──────────────────────────────────────────────────────────────


def test_zero_reward_rejected():
    decision = PolicyEngine.evaluate_reward(
        policy=None, reward=0, vault_total_supply=0, vault_max_supply=2**64 - 1
    )
    assert decision.allowed is False
    assert decision.reason == "zero_amount_mint"


def test_supply_cap_enforced_by_default():
    within = PolicyEngine.evaluate_reward(
        policy=None, reward=1_000, vault_total_supply=10_000, vault_max_supply=11_000
    )
    assert within.allowed is True

    over = PolicyEngine.evaluate_reward(
        policy=None, reward=1_000, vault_total_supply=10_000, vault_max_supply=10_400
    )
    assert over.allowed is False
    assert over.reason == "supply_limit_exceeded"


def test_supply_cap_can_be_relaxed():
    policy = _default_policy()
    policy.enforce_supply_cap = False
    decision = PolicyEngine.evaluate_reward(
        policy=policy, reward=1_000, vault_total_supply=10_000, vault_max_supply=10_000
    )
    assert decision.allowed is True


def test_reward_never_zero_even_if_supply_relaxed():
    policy = _default_policy()
    policy.enforce_supply_cap = False
    decision = PolicyEngine.evaluate_reward(
        policy=policy, reward=0, vault_total_supply=0, vault_max_supply=2**64 - 1
    )
    assert decision.allowed is False
    assert decision.reason == "zero_amount_mint"


# ── Config loading ───────────────────────────────────────────────────────────


def test_load_policy_defaults():
    policy = load_policy_config(env={})
    assert policy.mint_enabled is True
    assert policy.max_clock_skew_sec == 300
    assert policy.max_energy_bps == 10_000


def test_load_policy_env_overrides():
    policy = load_policy_config(
        env={"AXIS_POLICY_MAX_CLOCK_SKEW_SEC": "600", "AXIS_POLICY_MINT_ENABLED": "false"}
    )
    assert policy.max_clock_skew_sec == 600
    assert policy.mint_enabled is False


def test_load_policy_sanitizes_parameters():
    import pytest

    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_MAX_ENERGY_BPS": "0"})
    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_MAX_CLOCK_SKEW_SEC": "7200"})


# ── AI anomaly gate (Phase 1, ENRG-AI): opt-in off-chain extension ────────────


def _fake_signal(anomaly: bool, score: float):
    """A minimal duck-typed signal (the engine must not depend on axis_core.ai)."""

    return type(
        "_Fake",
        (),
        {
            "is_anomaly": anomaly,
            "score": score,
            "details": {"signals": ["power_spike"] if anomaly else []},
        },
    )()


def test_ai_anomaly_disabled_by_default_allows():
    policy = _default_policy()  # enforce_ai_anomaly defaults to False
    decision = PolicyEngine.evaluate_ai_anomaly(
        policy=policy, signal=_fake_signal(anomaly=True, score=1.0)
    )
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_ai_anomaly_none_policy_allows():
    decision = PolicyEngine.evaluate_ai_anomaly(
        policy=None, signal=_fake_signal(anomaly=True, score=1.0)
    )
    assert decision.allowed is True


def test_ai_anomaly_clean_signal_allows_when_enabled():
    policy = _default_policy()
    policy.enforce_ai_anomaly = True
    decision = PolicyEngine.evaluate_ai_anomaly(
        policy=policy, signal=_fake_signal(anomaly=False, score=0.0)
    )
    assert decision.allowed is True


def test_ai_anomaly_blocks_spiking_signal_when_enabled():
    policy = _default_policy()
    policy.enforce_ai_anomaly = True
    decision = PolicyEngine.evaluate_ai_anomaly(
        policy=policy, signal=_fake_signal(anomaly=True, score=1.0)
    )
    assert decision.allowed is False
    assert decision.reason == "ai_anomaly_flagged"
    assert decision.details["ai_score"] == 1.0
    assert decision.details["ai_signals"] == ["power_spike"]


def test_ai_anomaly_threshold_controls_rejection():
    policy = _default_policy()
    policy.enforce_ai_anomaly = True
    policy.ai_anomaly_threshold = 0.6

    low = PolicyEngine.evaluate_ai_anomaly(
        policy=policy, signal=_fake_signal(anomaly=True, score=0.4)
    )
    assert low.allowed is True

    high = PolicyEngine.evaluate_ai_anomaly(
        policy=policy, signal=_fake_signal(anomaly=True, score=0.9)
    )
    assert high.allowed is False


def test_ai_anomaly_explicit_threshold_override():
    policy = _default_policy()
    policy.enforce_ai_anomaly = True
    decision = PolicyEngine.evaluate_ai_anomaly(
        policy=policy,
        signal=_fake_signal(anomaly=True, score=0.5),
        threshold=0.4,
    )
    assert decision.allowed is False


def test_load_policy_ai_env_overrides():
    policy = load_policy_config(
        env={
            "AXIS_POLICY_ENFORCE_AI_ANOMALY": "true",
            "AXIS_POLICY_AI_ANOMALY_THRESHOLD": "0.75",
        }
    )
    assert policy.enforce_ai_anomaly is True
    assert policy.ai_anomaly_threshold == 0.75


def test_load_policy_sanitizes_ai_threshold():
    import pytest

    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_AI_ANOMALY_THRESHOLD": "1.5"})
    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_AI_ANOMALY_THRESHOLD": "abc"})


# ── Statement #87 (sterility index, ENRG-AI): opt-in off-chain gate ─────────


def _fake_sterility(a2: float, cv: float, verdict: str = "passed"):
    """A minimal duck-typed Statement #87 reading.

    The engine must not depend on ``agent.physics``: anything with ``a2``, ``cv``
    and ``details`` is a signal, exactly as ``_fake_signal`` stands in for the AI
    anomaly.
    """

    return type(
        "_Sterility",
        (),
        {"a2": a2, "cv": cv, "details": {"verdict": verdict}},
    )()


def test_sterility_disabled_by_default_allows():
    policy = _default_policy()  # enforce_sterility defaults to False
    decision = PolicyEngine.evaluate_sterility(
        policy=policy, signal=_fake_sterility(a2=0.0, cv=0.0, verdict="failed")
    )
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_sterility_none_policy_allows():
    decision = PolicyEngine.evaluate_sterility(
        policy=None, signal=_fake_sterility(a2=0.0, cv=0.0, verdict="failed")
    )
    assert decision.allowed is True


def test_sterility_blocks_unnaturally_exact_relief():
    policy = _default_policy()
    policy.enforce_sterility = True
    decision = PolicyEngine.evaluate_sterility(
        policy=policy, signal=_fake_sterility(a2=0.0, cv=0.175, verdict="failed")
    )
    assert decision.allowed is False
    assert decision.reason == "synthetic_collusion_detected"
    assert decision.details["sterility_a2"] == 0.0
    assert decision.details["sterility_cv"] == 0.175
    assert decision.details["sterility_a2_threshold"] == 0.1
    assert decision.details["sterility_cv_threshold"] == 0.005
    assert decision.details["sterility_verdict"] == "failed"


def test_sterility_blocks_flat_relief_through_the_variation_floor():
    policy = _default_policy()
    policy.enforce_sterility = True
    decision = PolicyEngine.evaluate_sterility(
        policy=policy, signal=_fake_sterility(a2=2.0, cv=0.001, verdict="failed")
    )
    assert decision.allowed is False
    assert decision.reason == "synthetic_collusion_detected"


def test_sterility_passes_lived_relief():
    policy = _default_policy()
    policy.enforce_sterility = True
    # Numbers a lived medium produces (consistency.jl, seed 1: A² = 8.20, CV = 0.175).
    decision = PolicyEngine.evaluate_sterility(
        policy=policy, signal=_fake_sterility(a2=8.204, cv=0.175, verdict="passed")
    )
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_sterility_missing_signal_is_not_a_rejection():
    policy = _default_policy()
    policy.enforce_sterility = True
    decision = PolicyEngine.evaluate_sterility(policy=policy, signal=None)
    assert decision.allowed is True


def test_sterility_thresholds_are_policy_not_signal():
    policy = _default_policy()
    policy.enforce_sterility = True
    # The same reading passes or fails depending on the policy alone.
    signal = _fake_sterility(a2=0.3, cv=0.2, verdict="passed")
    assert PolicyEngine.evaluate_sterility(policy=policy, signal=signal).allowed is True

    policy.sterility_a2_threshold = 0.5
    decision = PolicyEngine.evaluate_sterility(policy=policy, signal=signal)
    assert decision.allowed is False
    assert decision.reason == "synthetic_collusion_detected"


def test_sterility_explicit_threshold_override():
    policy = _default_policy()
    policy.enforce_sterility = True
    passed = PolicyEngine.evaluate_sterility(
        policy=policy,
        signal=_fake_sterility(a2=0.3, cv=0.2),
        a2_threshold=0.2,
        cv_threshold=0.1,
    )
    assert passed.allowed is True

    blocked = PolicyEngine.evaluate_sterility(
        policy=policy,
        signal=_fake_sterility(a2=0.3, cv=0.2),
        cv_threshold=0.25,
    )
    assert blocked.allowed is False


def test_load_policy_sterility_env_overrides():
    policy = load_policy_config(
        env={
            "AXIS_POLICY_ENFORCE_STERILITY": "true",
            "AXIS_POLICY_STERILITY_A2_THRESHOLD": "0.25",
            "AXIS_POLICY_STERILITY_CV_THRESHOLD": "0.01",
        }
    )
    assert policy.enforce_sterility is True
    assert policy.sterility_a2_threshold == 0.25
    assert policy.sterility_cv_threshold == 0.01


def test_load_policy_sanitizes_sterility_parameters():
    import pytest

    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_STERILITY_A2_THRESHOLD": "-1"})
    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_STERILITY_CV_THRESHOLD": "0"})
    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_STERILITY_CV_THRESHOLD": "abc"})


# ── Market trade gate (Phase 3): recommendation → authorized action ─────────


def _trading_producer(*, trade_enabled: bool = True) -> ProducerState:
    return ProducerState(
        device_id="dev_trader",
        state=DeviceState.ACTIVE,
        tier=DeviceTier.INDUSTRIAL,
        month_energy_wh=0,
        month_start_ts=1_000,
        trade_enabled=trade_enabled,
    )


def _rec(action: str = "SELL", volume_wh: float = 200.0):
    from axis_core.ai import Recommendation

    return Recommendation(action=action, volume_wh=volume_wh)


def test_trade_rejected_without_device_right():
    decision = PolicyEngine.evaluate_trade(
        policy=_default_policy(),
        recommendation=_rec(),
        producer=_trading_producer(trade_enabled=False),
    )
    assert decision.allowed is False
    assert decision.reason == "trade_not_authorized"


def test_trade_allowed_when_enabled_and_within_limits():
    policy = _default_policy()
    decision = PolicyEngine.evaluate_trade(
        policy=policy,
        recommendation=_rec(),
        producer=_trading_producer(),
    )
    assert decision.allowed is True
    assert decision.reason == "trade_allowed"
    assert decision.details["action"] == "SELL"


def test_trade_volume_limit_enforced():
    policy = _default_policy()
    policy.enforce_trade_limits = True
    policy.trade_max_volume_wh = 100
    decision = PolicyEngine.evaluate_trade(
        policy=policy,
        recommendation=_rec(volume_wh=200),
        producer=_trading_producer(),
    )
    assert decision.allowed is False
    assert decision.reason == "trade_volume_exceeded"
    assert decision.details["trade_max_volume_wh"] == 100


def test_trade_dao_gate():
    policy = _default_policy()
    policy.trade_requires_dao = True

    gated = PolicyEngine.evaluate_trade(
        policy=policy, recommendation=_rec(), producer=_trading_producer(), dao_approved=False
    )
    assert gated.allowed is False
    assert gated.reason == "trade_dao_gated"

    approved = PolicyEngine.evaluate_trade(
        policy=policy, recommendation=_rec(), producer=_trading_producer(), dao_approved=True
    )
    assert approved.allowed is True


def test_load_policy_trade_env():
    policy = load_policy_config(
        env={
            "AXIS_POLICY_ENFORCE_TRADE_LIMITS": "true",
            "AXIS_POLICY_TRADE_MAX_VOLUME_WH": "5000",
            "AXIS_POLICY_TRADE_REQUIRES_DAO": "true",
        }
    )
    assert policy.enforce_trade_limits is True
    assert policy.trade_max_volume_wh == 5000
    assert policy.trade_requires_dao is True


def test_load_policy_sanitizes_trade_volume():
    import pytest

    with pytest.raises(ValueError):
        load_policy_config(env={"AXIS_POLICY_TRADE_MAX_VOLUME_WH": "-5"})

