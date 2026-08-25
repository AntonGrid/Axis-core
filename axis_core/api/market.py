"""Market recommendation API (Phase 3, step B).

`POST /market/recommend` wires the full decision chain for one device:

    production forecast + storage + prices → Recommender (action)
        → Policy Engine (trade right / volume limits / DAO gate)

The Recommender only ranks; the returned ``trade_decision`` is the
authoritative answer (per ADR-0003, the AI never executes on its own).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from axis_core.ai import recommend
from axis_core.policy.config import load_policy_config
from axis_core.policy.engine import PolicyEngine
from axis_core.policy.models import ProducerState

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/recommend")
async def market_recommend(body: Dict[str, Any]) -> Dict[str, Any]:
    """Recommend and gate a market action for one device.

    Body:
        device_id, forecast_wh, storage_wh, capacity_wh, price_now,
        price_forecast, avg_price, trade_enabled, dao_approved
    """
    try:
        recommendation = recommend(
            forecast_wh=float(body.get("forecast_wh", 0.0)),
            storage_wh=float(body.get("storage_wh", 0.0)),
            capacity_wh=float(body.get("capacity_wh", 0.0)),
            price_now=float(body.get("price_now", 0.0)),
            price_forecast=float(body.get("price_forecast", 0.0)),
            avg_price=float(body.get("avg_price", 0.0)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid market inputs: {e}")

    policy = load_policy_config()
    producer = ProducerState(
        device_id=str(body.get("device_id", "dev")),
        trade_enabled=bool(body.get("trade_enabled", False)),
    )
    decision = PolicyEngine.evaluate_trade(
        policy=policy,
        recommendation=recommendation,
        producer=producer,
        dao_approved=bool(body.get("dao_approved", False)),
    )

    return {
        "device_id": producer.device_id,
        "recommendation": recommendation.to_dict(),
        "trade_decision": decision.to_dict(),
    }
