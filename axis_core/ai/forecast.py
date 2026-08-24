"""Generation forecast over device history (Phase 1).

A small, dependency-free linear model: least-squares fit over the device's
reported energy series, projected one horizon ahead. This is the *baseline*
signal; Phase 2 will combine local gateway models (federated learning) and
external weather feeds via the ENRG-AI aggregator.

Forecasts are signals too: ``forecast_production`` never trades or decides —
it only produces an observation for the Policy Engine / DAO.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ForecastResult:
    """Projected next-period production for one device."""

    device_id: str
    forecast_wh: Optional[float]
    horizon_h: int
    samples: int
    details: Dict[str, Any]


def _linear_fit(xs: List[float], ys: List[float]) -> tuple:
    """Least-squares line through points; returns ``(slope, intercept)``."""
    n = len(xs)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, y_mean
    slope = numerator / denominator
    return slope, y_mean - slope * x_mean


def forecast_production(
    device_id: str,
    history: List[Dict[str, Any]],
    horizon_h: int = 24,
    future_points: int = 1,
) -> ForecastResult:
    """Forecast the next reported production value from the energy series.

    Args:
        device_id: the device being observed.
        history: chronological list of report dicts; only ``energy_wh``
            entries are used.
        horizon_h: label for the projection horizon (informational).
        future_points: how many steps ahead to project.

    Returns:
        ``forecast_wh=None`` when fewer than 2 energy samples are available
        (not enough data — a neutral, no-op forecast).
    """
    energies = [float(h["energy_wh"]) for h in history if h.get("energy_wh") is not None]
    if len(energies) < 2:
        return ForecastResult(
            device_id=device_id,
            forecast_wh=None,
            horizon_h=horizon_h,
            samples=len(energies),
            details={"reason": "not enough samples"},
        )

    slope, intercept = _linear_fit(list(range(len(energies))), energies)
    next_index = len(energies) - 1 + future_points
    forecast = intercept + slope * next_index

    return ForecastResult(
        device_id=device_id,
        forecast_wh=round(max(0.0, forecast), 2),
        horizon_h=horizon_h,
        samples=len(energies),
        details={
            "slope": round(slope, 4),
            "intercept": round(intercept, 2),
            "trend": "up" if slope > 0 else ("down" if slope < 0 else "flat"),
        },
    )

