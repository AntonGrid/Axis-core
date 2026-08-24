"""Generation forecast (Phase 1).

Phase 0 scaffold: combines local gateway models and external data
(weather feeds) into an energy production forecast. No-op until Phase 1.
"""
from __future__ import annotations

from typing import Any, Dict


def forecast_production(
    device_id: str,
    history: list,
    external: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Placeholder for production forecast."""
    return {
        "device_id": device_id,
        "forecast_kwh": None,
        "horizon_h": 24,
        "reason": "not implemented (Phase 1)",
    }
