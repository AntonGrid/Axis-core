"""Policy configuration loading (ADR-0003: limits are parameters, not hardcoded).

Precedence: environment variables > policy config file > defaults — the same
precedence used by the ENRG oracle ``policy.js``.

Environment variables (prefix ``AXIS_POLICY_``):

- ``AXIS_POLICY_MINT_ENABLED``           (bool)
- ``AXIS_POLICY_ENFORCE_ORACLE_WHITELIST`` (bool)
- ``AXIS_POLICY_ENFORCE_DEVICE_STATE``   (bool)
- ``AXIS_POLICY_ENFORCE_TIER_LIMITS``    (bool)
- ``AXIS_POLICY_ENFORCE_ENERGY_CAPS``    (bool)
- ``AXIS_POLICY_ENFORCE_SUPPLY_CAP``     (bool)
- ``AXIS_POLICY_MAX_ENERGY_BPS``         (int, 0 < v <= 1_000_000)
- ``AXIS_POLICY_MAX_CLOCK_SKEW_SEC``     (int, 0 <= v <= 3600)
- ``AXIS_POLICY_FILE``                   (path to a JSON policy config)

The reference service defaults intentionally use relaxed values for
``enforce_*`` because the Axis Core registry uses the simplified lifecycle
subset (``docs/conformance.md`` §2.3): there is no on-chain ``Active`` state
to gate, no tier accounting and no rated power. The full on-chain defaults
(``enforce_* = True``) are enforced by the ENRG deployment profile.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from axis_core.policy.models import PolicyRegistry

#: Reference service defaults (see module docstring for the rationale).
DEFAULT_POLICY = PolicyRegistry(
    authority="",
    mint_enabled=True,
    enforce_oracle_whitelist=False,
    enforce_device_state=False,
    enforce_tier_limits=False,
    enforce_energy_caps=False,
    enforce_supply_cap=True,
    max_energy_bps=10_000,
    max_clock_skew_sec=300,
    version=1,
    updated_at=0,
)

_BOOL_ENV = {
    "mint_enabled": "AXIS_POLICY_MINT_ENABLED",
    "enforce_oracle_whitelist": "AXIS_POLICY_ENFORCE_ORACLE_WHITELIST",
    "enforce_device_state": "AXIS_POLICY_ENFORCE_DEVICE_STATE",
    "enforce_tier_limits": "AXIS_POLICY_ENFORCE_TIER_LIMITS",
    "enforce_energy_caps": "AXIS_POLICY_ENFORCE_ENERGY_CAPS",
    "enforce_supply_cap": "AXIS_POLICY_ENFORCE_SUPPLY_CAP",
}
_INT_ENV = {
    "max_energy_bps": "AXIS_POLICY_MAX_ENERGY_BPS",
    "max_clock_skew_sec": "AXIS_POLICY_MAX_CLOCK_SKEW_SEC",
}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_policy_config(
    env: Optional[Dict[str, str]] = None,
    policy_file: Optional[str] = None,
) -> PolicyRegistry:
    """Load the active policy set.

    ``env`` defaults to ``os.environ``. ``policy_file`` overrides the
    ``AXIS_POLICY_FILE`` env var when explicitly provided. Returns a fully
    populated ``PolicyRegistry`` (all fields filled).
    """
    env = env if env is not None else os.environ
    policy = PolicyRegistry.from_dict(DEFAULT_POLICY.to_dict())

    file_path = policy_file or env.get("AXIS_POLICY_FILE", "").strip()
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {**policy.to_dict(), **{k: v for k, v in data.items() if k in policy.to_dict()}}
        policy = PolicyRegistry.from_dict(merged)

    for key, var in _BOOL_ENV.items():
        if env.get(var):
            setattr(policy, key, _parse_bool(env[var]))

    for key, var in _INT_ENV.items():
        if env.get(var):
            try:
                setattr(policy, key, int(env[var]))
            except ValueError:
                raise ValueError(f"{var} must be an integer, got {env[var]!r}") from None

    # Parameter sanitization (mirrors on-chain update_policy).
    if not (0 < policy.max_energy_bps <= 1_000_000):
        raise ValueError("max_energy_bps must be in (0, 1_000_000]")
    if not (0 <= policy.max_clock_skew_sec <= 3600):
        raise ValueError("max_clock_skew_sec must be in [0, 3600]")

    return policy
