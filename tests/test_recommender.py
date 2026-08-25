"""Market recommender tests (axis_core.ai.recommender)."""

import pytest

from axis_core.ai import recommend


def test_sell_on_overflow():
    rec = recommend(
        forecast_wh=300, storage_wh=900, capacity_wh=1000,
        price_now=0.10, price_forecast=0.10,
    )
    assert rec.action == "SELL"
    assert rec.volume_wh == pytest.approx(200.0)
    assert rec.confidence > 0.0


def test_store_when_price_rises():
    rec = recommend(
        forecast_wh=100, storage_wh=500, capacity_wh=1000,
        price_now=0.10, price_forecast=0.15,
    )
    assert rec.action == "STORE"
    assert rec.confidence > 0.0


def test_buy_when_storage_low_and_price_cheap():
    rec = recommend(
        forecast_wh=0, storage_wh=50, capacity_wh=1000,
        price_now=0.08, avg_price=0.12,
        price_forecast=0.08,
    )
    assert rec.action == "BUY"
    assert rec.volume_wh == pytest.approx(150.0)  # 20% of capacity - storage


def test_hold_when_nothing_is_profitable():
    rec = recommend(
        forecast_wh=100, storage_wh=500, capacity_wh=1000,
        price_now=0.10, price_forecast=0.10, avg_price=0.10,
    )
    assert rec.action == "HOLD"
    assert rec.confidence == 0.0


def test_sell_has_priority_over_store():
    # Both overflow AND an upcoming price rise: the surplus must be sold.
    rec = recommend(
        forecast_wh=400, storage_wh=900, capacity_wh=1000,
        price_now=0.10, price_forecast=0.20,
    )
    assert rec.action == "SELL"
    assert rec.volume_wh == pytest.approx(300.0)


def test_store_requires_stored_energy():
    rec = recommend(
        forecast_wh=100, storage_wh=0, capacity_wh=1000,
        price_now=0.10, price_forecast=0.20,
    )
    assert rec.action == "HOLD"  # nothing stored to hold


def test_buy_requires_average_price():
    rec = recommend(
        forecast_wh=0, storage_wh=50, capacity_wh=1000,
        price_now=0.08, avg_price=0.0, price_forecast=0.08,
    )
    assert rec.action == "HOLD"


def test_invalid_capacity_raises():
    with pytest.raises(ValueError):
        recommend(forecast_wh=0, storage_wh=0, capacity_wh=0, price_now=0.1, price_forecast=0.1)


def test_confidence_is_bounded():
    rec = recommend(
        forecast_wh=10_000, storage_wh=0, capacity_wh=100,
        price_now=0.1, price_forecast=0.1,
    )
    assert rec.action == "SELL"
    assert 0.0 <= rec.confidence <= 1.0


def test_to_dict_shape():
    rec = recommend(
        forecast_wh=300, storage_wh=900, capacity_wh=1000,
        price_now=0.1, price_forecast=0.1,
    )
    data = rec.to_dict()
    assert data["action"] == "SELL"
    assert "volume_wh" in data and "confidence" in data and "rationale" in data
