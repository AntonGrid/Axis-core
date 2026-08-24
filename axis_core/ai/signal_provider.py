"""SignalProvider — single entry point for AI signals (Phase 0 stub).

Constitution (ADR-0003): signals are **observations**, never decisions.
The Policy Engine decides; this provider only describes what the AI layer
observed. In Phase 0 it always returns a ``neutral`` signal, which is the
behavioral no-op: wiring it into the oracle changes nothing until policies
opt in via ``enforce_ai_anomaly`` / ``ai_anomaly_threshold`` (Phase 1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Signal:
    """A single AI observation, ready for the Policy Engine to consume.

    Attributes:
        level: ``neutral`` | ``info`` | ``warning`` | ``anomaly``.
        kind:  ``none`` | ``ai_anomaly`` | ``forecast`` | ``market``.
        score: confidence in [0, 1]; 0.0 for a neutral no-op signal.
        details: structured observation payload (device id, history, ...).
    """

    level: str = "neutral"
    kind: str = "none"
    score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_anomaly(self) -> bool:
        """True when the signal flags the device as anomalous."""
        return self.level == "anomaly"


class SignalProvider:
    """Provides AI signals to the oracle.

    Phase 0: returns a neutral no-op signal for every call. The signature is
    the future-proof contract — ``report`` is the cryptographically verified
    oracle report, ``history`` the device history from the registry,
    ``market`` the normalized market feeds.
    """

    def evaluate(
        self,
        *,
        device_id: str,
        report: Optional[Dict[str, Any]] = None,
        history: Optional[list] = None,
        market: Optional[Dict[str, Any]] = None,
    ) -> Signal:
        return Signal(
            level="neutral",
            kind="none",
            score=0.0,
            details={"device_id": device_id},
        )
