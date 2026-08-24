"""Anomaly detection over device history (Phase 1).

Phase 0 scaffold: the module exists so the package layout is complete and
tests can import it. Behavior will combine statistical and ML signals over
the device report history (energy, ERS, nonce) from the registry.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def detect_anomaly(
    device_id: str,
    history: Optional[List[Dict[str, Any]]] = None,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Placeholder for anomaly detection.

    Returns a neutral observation dict (no anomaly) until Phase 1.
    """
    return {
        "device_id": device_id,
        "anomaly": False,
        "score": 0.0,
        "reason": "not implemented (Phase 1)",
    }
