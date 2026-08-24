"""Market price feeds (Phase 3).

Phase 0 scaffold: normalized energy price feeds (day-ahead exchange, P2P
benchmarks), caching and periodic refresh. No-op until Phase 3.
"""
from __future__ import annotations

from typing import Any, Dict


def current_prices() -> Dict[str, Any]:
    """Placeholder for normalized market prices."""
    return {"prices": [], "source": "none", "reason": "not implemented (Phase 3)"}
