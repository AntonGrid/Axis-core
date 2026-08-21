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

