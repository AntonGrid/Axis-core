"""Market recommender — combines generation, storage and prices into actions.

Per ADR-0003 / GLOBAL_AI_ARCHITECTURE §6 the Recommender is **still a signal
source**: it ranks actions (``SELL / STORE / BUY / HOLD``) with a confidence,
but it never executes. The Policy Engine (``evaluate_trade``) decides whether
the device may act, within limits and DAO gates.

Pure function, deterministic, fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

#: Minimum expected price increase for STORE to beat selling now.
DEFAULT_STORE_THRESHOLD = 1.05
#: Fraction of capacity below which storage is considered "low" for BUY.
DEFAULT_MIN_STORAGE_RATIO = 0.2
#: Buy only when the current price is this much below the recent average.
DEFAULT_BUY_DISCOUNT = 0.95


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class Recommendation:
    """A ranked market action for one device, ready for policy review."""

    action: str  # SELL | STORE | BUY | HOLD
    volume_wh: float = 0.0
    confidence: float = 0.0
    rationale: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "volume_wh": round(self.volume_wh, 2),
            "confidence": round(self.confidence, 3),
            "rationale": self.rationale,
            **self.details,
        }


def recommend(
    *,
    forecast_wh: float,
    storage_wh: float,
    capacity_wh: float,
    price_now: float,
    price_forecast: float,
    avg_price: float = 0.0,
    store_threshold: float = DEFAULT_STORE_THRESHOLD,
    min_storage_ratio: float = DEFAULT_MIN_STORAGE_RATIO,
    buy_discount: float = DEFAULT_BUY_DISCOUNT,
) -> Recommendation:
    """Rank the best market action for the next period.

    Args:
        forecast_wh: expected production over the period.
        storage_wh: current stored energy.
        capacity_wh: storage capacity (must be > 0).
        price_now: current market price (USD/kWh).
        price_forecast: expected price over the period (USD/kWh).
        avg_price: recent average price; used for the BUY signal.
        store_threshold: price growth factor that justifies STORE.
        min_storage_ratio: storage fill fraction considered "low".
        buy_discount: price / avg_price below which buying is attractive.
    """
    if capacity_wh <= 0:
        raise ValueError("capacity_wh must be positive")
    if price_now <= 0:
        raise ValueError("price_now must be positive")

    available = storage_wh + forecast_wh
    overflow = available - capacity_wh

    # 1. Overflow: storage is full — sell the surplus now.
    if overflow > 0:
        return Recommendation(
            action="SELL",
            volume_wh=overflow,
            confidence=_clamp(overflow / max(capacity_wh, 1.0)),
            rationale="generation exceeds storage capacity",
            details={"available_wh": available, "capacity_wh": capacity_wh},
        )

    # 2. Price is about to rise and we have something to store — keep it.
    if price_forecast > price_now * store_threshold and storage_wh > 0:
        rise = price_forecast / price_now - store_threshold
        return Recommendation(
            action="STORE",
            volume_wh=0.0,
            confidence=_clamp(rise / 0.2),
            rationale="price expected to rise; store instead of selling now",
            details={"price_rise_pct": round((price_forecast / price_now - 1.0) * 100, 2)},
        )

    # 3. Storage is low and energy is cheap — buy to top up.
    target = min_storage_ratio * capacity_wh
    if storage_wh < target and avg_price > 0 and price_now < avg_price * buy_discount:
        discount = 1.0 - price_now / avg_price
        return Recommendation(
            action="BUY",
            volume_wh=target - storage_wh,
            confidence=_clamp(discount / 0.1),
            rationale="storage low and price below average",
            details={"target_storage_wh": round(target, 2), "discount_pct": round(discount * 100, 2)},
        )

    return Recommendation(
        action="HOLD",
        rationale="no profitable action within policy thresholds",
        details={"available_wh": round(available, 2)},
    )
