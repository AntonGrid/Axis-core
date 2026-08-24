"""Anomaly detection over device history (Phase 1).

Behavioral analysis of the device's report history from the registry:
unexpected spikes in reported values (energy / max power) and nonce jumps.
Pure functions, no I/O — the Verifier (``axis_core.api.oracle``) feeds the
history, and the Policy Engine decides what (if anything) to do with the
result.

Constitution (ADR-0003): an anomaly is a **signal**, never a decision.
``detect_anomaly`` only observes; blocking/quarantine is a policy choice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, List

#: A single anomaly is flagged when the latest value deviates from the
#: median of the previous values by more than this factor.
SPIKE_FACTOR = 2.0

#: Nonce gaps larger than this many missing nonces count as a signal.
#: A gap of 1 (one skipped nonce) is tolerated (retries); larger gaps are
#: flagged (potentially skipped/stolen proofs).
NONCE_GAP_TOLERANCE = 1

#: Minimum samples before any spike signal is computed.
MIN_SPIKE_SAMPLES = 4

#: Default anomaly threshold for ``is_anomaly`` (score in [0, 1]).
DEFAULT_THRESHOLD = 0.5


@dataclass
class AnomalyResult:
    """Observation about one device, ready for policy evaluation."""

    device_id: str
    is_anomaly: bool
    score: float
    signals: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


def _median_of(values: List[float]) -> float:
    return float(median(values))


def _spike_signal(name: str, values: List[float]) -> tuple:
    """Return ``(signal_name, score)`` if the last value spikes vs. median
    of the previous values; ``(None, 0.0)`` otherwise.

    ``values`` is the full series; the last element is the current report.
    """
    if len(values) < MIN_SPIKE_SAMPLES:
        return None, 0.0

    current = values[-1]
    base = _median_of(values[:-1])
    if base <= 0:
        return None, 0.0

    ratio = current / base
    if ratio >= SPIKE_FACTOR:
        score = min(1.0, (ratio - 1.0) / (SPIKE_FACTOR - 1.0))
        return name, round(score, 3)
    return None, 0.0


def detect_anomaly(
    device_id: str,
    history: List[Dict[str, Any]],
    threshold: float = DEFAULT_THRESHOLD,
) -> AnomalyResult:
    """Analyze a device's report history and flag behavioral anomalies.

    Args:
        device_id: the device being observed.
        history: chronological list of report dicts. Recognized fields:
            ``nonce`` (int), ``energy_wh`` (int/float), ``max_power_kw``
            (int/float). Any subset works — only present fields are analyzed.
        threshold: score in ``[0, 1]`` above which ``is_anomaly`` becomes True.

    Returns:
        An ``AnomalyResult`` with the observation (``is_anomaly`` is the
        *signal*, not a decision).
    """
    if not history:
        return AnomalyResult(device_id, is_anomaly=False, score=0.0, details={"samples": 0})

    signals: List[str] = []
    score = 0.0
    details: Dict[str, Any] = {"samples": len(history)}

    # 1. Reported energy spike (future-proof; the current attestation API
    #    does not carry energy yet, so this typically stays silent).
    energies = [float(h["energy_wh"]) for h in history if h.get("energy_wh") is not None]
    if len(energies) >= MIN_SPIKE_SAMPLES:
        sig, s = _spike_signal("energy_spike", energies)
        if sig:
            signals.append(sig)
            score = max(score, s)
            details["energy_ratio_vs_median"] = round(energies[-1] / _median_of(energies[:-1]), 3)

    # 2. Reported max_power spike (present in the current attestation API).
    powers = [float(h["max_power_kw"]) for h in history if h.get("max_power_kw") is not None]
    if len(powers) >= MIN_SPIKE_SAMPLES:
        sig, s = _spike_signal("power_spike", powers)
        if sig:
            signals.append(sig)
            score = max(score, s)
            details["power_ratio_vs_median"] = round(powers[-1] / _median_of(powers[:-1]), 3)

    # 3. Nonce jumps (skipped proofs are suspicious).
    nonces = [int(h["nonce"]) for h in history if h.get("nonce") is not None]
    if len(nonces) >= 2:
        gap = nonces[-1] - nonces[-2]
        if gap > NONCE_GAP_TOLERANCE:
            signals.append("nonce_gap")
            details["nonce_gap"] = gap
            score = max(score, min(1.0, gap / 5.0))

    return AnomalyResult(
        device_id=device_id,
        is_anomaly=score >= threshold,
        score=round(min(1.0, score), 3),
        signals=sorted(signals),
        details=details,
    )

