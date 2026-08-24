"""SignalProvider — single entry point for AI signals (Phase 1).

Constitution (ADR-0003): signals are **observations**, never decisions.
The Policy Engine decides; this provider only describes what the AI layer
observed.

- No history  → ``neutral`` no-op (the Phase 0 behavior).
- With history → anomaly analysis (``anomaly.detect_anomaly``) and a
  production forecast (``forecast.forecast_production``). When an anomaly is
  detected the signal level is ``anomaly``; the oracle may then consult the
  Policy Engine (``enforce_ai_anomaly`` / ``ai_anomaly_threshold``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from axis_core.ai.anomaly import DEFAULT_THRESHOLD, AnomalyResult, detect_anomaly
from axis_core.ai.forecast import ForecastResult, forecast_production


@dataclass
class Signal:
    """A single AI observation, ready for the Policy Engine to consume.

    Attributes:
        level: ``neutral`` | ``info`` | ``warning`` | ``anomaly``.
        kind:  ``none`` | ``ai_anomaly`` | ``forecast`` | ``market``.
        score: confidence in [0, 1]; 0.0 for a neutral no-op signal.
        details: structured observation payload (device id, signals, forecast).
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

    ``evaluate`` is the future-proof contract: ``report`` is the
    cryptographically verified oracle report, ``history`` the device history
    from the registry, ``market`` the normalized market feeds.
    """

    def __init__(self, anomaly_threshold: float = DEFAULT_THRESHOLD) -> None:
        self.anomaly_threshold = anomaly_threshold

    def evaluate_anomaly(
        self,
        *,
        device_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AnomalyResult:
        """Anomaly observation over the device history (or a no-op)."""
        return detect_anomaly(device_id, history or [], threshold=self.anomaly_threshold)

    def evaluate_forecast(
        self,
        *,
        device_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
        horizon_h: int = 24,
    ) -> ForecastResult:
        """Production forecast observation (or a no-op without enough data)."""
        return forecast_production(device_id, history or [], horizon_h=horizon_h)

    def evaluate(
        self,
        *,
        device_id: str,
        report: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        market: Optional[Dict[str, Any]] = None,
        horizon_h: int = 24,
    ) -> Signal:
        history = history or []
        anomaly = self.evaluate_anomaly(device_id=device_id, history=history)
        forecast = self.evaluate_forecast(
            device_id=device_id, history=history, horizon_h=horizon_h
        )

        details: Dict[str, Any] = {
            "device_id": device_id,
            "anomaly_score": anomaly.score,
            "anomaly_signals": anomaly.signals,
            "forecast_wh": forecast.forecast_wh,
            "forecast_trend": forecast.details.get("trend"),
        }

        if anomaly.is_anomaly:
            return Signal(
                level="anomaly",
                kind="ai_anomaly",
                score=anomaly.score,
                details=details,
            )

        if history:
            return Signal(
                level="info",
                kind="forecast",
                score=0.0,
                details=details,
            )

        return Signal(level="neutral", kind="none", score=0.0, details={"device_id": device_id})

