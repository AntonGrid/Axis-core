"""AI signal layer (ENRG-AI integration).

Per ADR-0003 the AI oracle is a **source of signals, not decisions**.
This package produces verifiable observations (anomaly, forecast, market)
that the Policy Engine **may** consume. A signal never blocks or mints by
itself: the decision belongs to ``axis_core.policy``.

Phase 1 ships the real anomaly analysis and production forecast; the market
feeds arrive in Phase 3.
"""

from axis_core.ai.anomaly import (
    DEFAULT_THRESHOLD,
    MIN_SPIKE_SAMPLES,
    NONCE_GAP_TOLERANCE,
    SPIKE_FACTOR,
    AnomalyResult,
    detect_anomaly,
)
from axis_core.ai.forecast import ForecastResult, forecast_production
from axis_core.ai.recommender import Recommendation, recommend
from axis_core.ai.signal_provider import Signal, SignalProvider

__all__ = [
    "DEFAULT_THRESHOLD",
    "MIN_SPIKE_SAMPLES",
    "NONCE_GAP_TOLERANCE",
    "SPIKE_FACTOR",
    "AnomalyResult",
    "ForecastResult",
    "Recommendation",
    "Signal",
    "SignalProvider",
    "detect_anomaly",
    "forecast_production",
    "recommend",
]

