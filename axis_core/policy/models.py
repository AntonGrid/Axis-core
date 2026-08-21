"""Domain-neutral policy state models (ADR-0003).

These models mirror the on-chain Policy Engine of the ENRG reference
implementation so that the off-chain oracle and the on-chain verifier agree on
what a decision is and on the policy parameters:

- ``DeviceState``  — ``programs/enrg-mvp/src/state/producer.rs`` (ADR-0005);
- ``DeviceTier``   — ``programs/enrg-mvp/src/state/producer.rs`` (v7.0 §15);
- ``PolicyRegistry`` — ``programs/enrg-mvp/src/state/policy.rs``.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

#: Mirrors the on-chain ``DeviceState`` enum (ADR-0005).
class DeviceState(str, enum.Enum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    CLAIMED = "claimed"
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    QUARANTINE = "quarantine"
    MAINTENANCE = "maintenance"
    REVOKED = "revoked"

    def can_mint(self) -> bool:
        """Only ``Active`` devices may mint (ADR-0005)."""
        return self is DeviceState.ACTIVE


#: Device trust level (v7.0 §15 — Device Trust Levels).
class DeviceTier(str, enum.Enum):
    BASIC = "basic"
    VERIFIED = "verified"
    INDUSTRIAL = "industrial"
    INSTITUTIONAL = "institutional"

    def monthly_limit_wh(self) -> Optional[int]:
        """Monthly minting limit in Wh; ``None`` means no limit.

        Mirrors on-chain ``constants.rs``: BASIC_MONTHLY_LIMIT_WH = 100_000
        (100 kWh), VERIFIED_MONTHLY_LIMIT_WH = 10_000_000 (10 MWh).
        """
        return _TIER_MONTHLY_LIMITS_WH[self]

    def allows_increment(self, month_energy_wh: int, report_energy_wh: int) -> bool:
        """Whether ``month_energy + report_energy <= limit`` (v7.0 §15)."""
        limit = self.monthly_limit_wh()
        if limit is None:
            return True
        return month_energy_wh + report_energy_wh <= limit

    def is_premium(self) -> bool:
        """Premium tier flag (ENRG Market premium access, v7.0 §30)."""
        return self in (DeviceTier.INDUSTRIAL, DeviceTier.INSTITUTIONAL)


#: Monthly minting limits (Wh) per tier. ``None`` means no limit.
#: (Module-level so the str-mixin enum does not turn it into a member.)
_TIER_MONTHLY_LIMITS_WH = {
    DeviceTier.BASIC: 100_000,
    DeviceTier.VERIFIED: 10_000_000,
    DeviceTier.INDUSTRIAL: None,
    DeviceTier.INSTITUTIONAL: None,
}


@dataclass
class ProducerState:
    """The Device Registry subset the Policy Engine needs.

    Mirrors the on-chain ``EnergyProducer`` fields consumed by
    ``PolicyEngine::evaluate_preamble``.
    """

    device_id: str
    state: DeviceState = DeviceState.PROVISIONED
    tier: DeviceTier = DeviceTier.BASIC
    month_energy_wh: int = 0
    month_start_ts: int = 0
    revoked: bool = False
    #: Device rated power (Wh) for the energy cap (domain profile).
    rated_power_wh: int = 10_000

    def effective_month_energy(self, now: int) -> int:
        """Rolling 30-day window; returns 0 when the window has reset."""
        if now - self.month_start_ts >= 30 * 24 * 3600:
            return 0
        return self.month_energy_wh

    def can_mint(self, now: int) -> bool:
        """ADR-0005 gating: ``Active`` state and (if limited) tier headroom."""
        if self.revoked or not self.state.can_mint():
            return False
        limit = self.tier.monthly_limit_wh()
        if limit is None:
            return True
        return self.effective_month_energy(now) < limit


@dataclass
class OracleReport:
    """A report subject to policy evaluation (mirror of on-chain ``OracleReport``)."""

    device_id: str
    nonce: int
    device_timestamp: int
    verified_at: int
    energy_wh: int
    oracle: str = "oracle_main_1"


@dataclass
class PolicyRegistry:
    """On-chain Policy Registry snapshot.

    Mirrors ``programs/enrg-mvp/src/state/policy.rs``. All values are optional
    so that a partial snapshot behaves like the on-chain ``Option<&PolicyRegistry>``
    (``None`` fields fall back to the protocol defaults).
    """

    authority: str = ""
    mint_enabled: bool = True
    enforce_oracle_whitelist: bool = True
    enforce_device_state: bool = True
    enforce_tier_limits: bool = True
    enforce_energy_caps: bool = True
    enforce_supply_cap: bool = True
    max_energy_bps: int = 10_000
    max_clock_skew_sec: int = 300
    version: int = 1
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRegistry":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class PolicyDecision:
    """Stable result of a policy evaluation.

    ``allowed`` and ``reason`` mirror the oracle API decision shape
    (``{"allowed": ..., "reason": ...}``); ``details`` carries extra context
    (e.g. ``limit_kw``, ``max_energy_wh``).
    """

    allowed: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, **self.details}

    @classmethod
    def allowed_ok(cls) -> "PolicyDecision":
        return cls(allowed=True, reason="ok")
