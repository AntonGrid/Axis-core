"""Policy Engine (ADR-0003) — a single decision point for proof admissibility.

The Verifier (``axis_core.api.oracle``) is an **executor**: it performs the
cryptography (signature verification) and data transport. Every admissibility
decision (freshness, device state, tier/energy limits, supply cap) is made by
the Policy Engine in this package, mirroring the on-chain ``PolicyEngine`` of
the ENRG reference implementation
(``programs/enrg-mvp/src/instructions/policy_engine.rs``).

Components:

- ``models`` — domain-neutral state models mirroring the on-chain ``DeviceState``,
  ``DeviceTier`` and ``PolicyRegistry`` accounts;
- ``engine`` — ``PolicyEngine.evaluate_preamble`` / ``evaluate_reward``,
  behavior-identical to the on-chain decision function;
- ``config`` — policy parameter loading (env > config file > defaults).
"""

from axis_core.policy.config import DEFAULT_POLICY, load_policy_config
from axis_core.policy.engine import PolicyEngine, PolicyError
from axis_core.policy.models import (
    DeviceState,
    DeviceTier,
    OracleReport,
    PolicyDecision,
    PolicyRegistry,
    ProducerState,
)

__all__ = [
    "DEFAULT_POLICY",
    "DeviceState",
    "DeviceTier",
    "OracleReport",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyError",
    "PolicyRegistry",
    "ProducerState",
    "load_policy_config",
]
