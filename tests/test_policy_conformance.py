"""Conformance: the Axis-core Policy Engine must return the SHARED decisions.

The neutral contract is ``tests/conformance/policy_vectors.json`` in the ENRG
repository (the same file the on-chain Rust engine is asserted against by
``programs/enrg-mvp/tests/policy_conformance.rs``). Both engines implement the
semantics of ADR-0003 / ADR-0006; nothing else forced them to agree, so a drift in
either direction now turns CI red.

Locating the vectors (first hit wins):

1. ``$AXIS_CONFORMANCE_VECTORS`` — an explicit path (use this in CI);
2. ``../ENRG/tests/conformance/policy_vectors.json`` — a sibling checkout;
3. otherwise the test **skips** with a message (the ENRG repository is a separate
   artifact and this suite must not fail because it is absent).

Engine mechanics asserted here as well: an empty/absent ``policy`` object means
"protocol defaults" and a partially-specified policy keeps the dataclass defaults —
the unset flags stay TRUE, they do not become false.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from axis_core.policy.engine import PolicyEngine
from axis_core.policy.models import (
    DeviceState,
    DeviceTier,
    OracleReport,
    PolicyRegistry,
    ProducerState,
)

DEVICE_ID = "dev_conformance0000"


def _vectors_path() -> Optional[Path]:
    env = os.environ.get("AXIS_CONFORMANCE_VECTORS")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    # <workspace>/Axis-core/tests/ -> parents[2] = <workspace>
    sibling = Path(__file__).resolve().parents[2] / "ENRG/tests/conformance/policy_vectors.json"
    return sibling if sibling.is_file() else None


@pytest.fixture(scope="module")
def vectors() -> Dict[str, Any]:
    path = _vectors_path()
    if path is None:
        pytest.skip(
            "conformance vectors not found — set AXIS_CONFORMANCE_VECTORS to "
            "ENRG/tests/conformance/policy_vectors.json to run this suite"
        )
    with path.open() as fh:
        return json.load(fh)


def _policy(raw: Optional[Dict[str, Any]]) -> Optional[PolicyRegistry]:
    """Empty/missing policy -> None (protocol defaults); partial -> the rest default."""
    if not raw:
        return None
    return PolicyRegistry(**raw)


def _producer(raw: Dict[str, Any]) -> ProducerState:
    return ProducerState(
        device_id=DEVICE_ID,
        state=DeviceState(raw["state"]),
        tier=DeviceTier(raw["tier"]),
        month_energy_wh=raw["month_energy_wh"],
        month_start_ts=raw["month_start_ts"],
        revoked=raw["revoked"],
        rated_power_wh=raw["rated_power_wh"],
    )


def _report(raw: Dict[str, Any]) -> OracleReport:
    r = raw["report"]
    return OracleReport(
        device_id=DEVICE_ID,
        nonce=1,
        device_timestamp=r["verified_at"],
        verified_at=r["verified_at"],
        energy_wh=r["energy_wh"],
    )


def _decide(vector: Dict[str, Any], policy: Optional[PolicyRegistry]):
    kind = vector["kind"]
    if kind == "preamble":
        return PolicyEngine.evaluate_preamble(
            policy=policy,
            producer=_producer(vector["producer"]),
            report=_report(vector),
            now=vector["now"],
            oracle_trusted=vector["oracle_trusted"],
        )
    if kind == "reward":
        return PolicyEngine.evaluate_reward(
            policy=policy,
            reward=vector["reward"],
            vault_total_supply=vector["vault_total_supply"],
            vault_max_supply=vector["vault_max_supply"],
        )
    pytest.fail(f"unknown vector kind: {kind}")


def test_policy_engine_matches_the_conformance_vectors(vectors):
    cases = vectors["vectors"]
    assert len(cases) >= 18, f"the vector set shrank unexpectedly ({len(cases)})"

    checked = 0
    for vector in cases:
        decision = _decide(vector, _policy(vector.get("policy")))
        expected = vector["expected"]
        assert decision.allowed is expected["allowed"], (
            f"[{vector['id']}] allowed mismatch: got {decision.allowed}, "
            f"reason={decision.reason}"
        )
        assert decision.reason == expected["reason"], (
            f"[{vector['id']}] reason mismatch: got {decision.reason!r}, "
            f"expected {expected['reason']!r}"
        )
        checked += 1

    assert checked == len(cases)
