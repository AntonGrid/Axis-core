"""Market API tests — recommendation + trade gate end-to-end."""

from fastapi.testclient import TestClient

from axis_core.main import app

client = TestClient(app)


def _body(**overrides):
    body = {
        "device_id": "dev_1",
        "forecast_wh": 300.0,
        "storage_wh": 900.0,
        "capacity_wh": 1000.0,
        "price_now": 0.10,
        "price_forecast": 0.10,
        "avg_price": 0.10,
        "trade_enabled": True,
        "dao_approved": False,
    }
    body.update(overrides)
    return body


def test_recommend_sell_and_allowed():
    resp = client.post("/market/recommend", json=_body())
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommendation"]["action"] == "SELL"
    assert data["recommendation"]["volume_wh"] == 200.0
    assert data["trade_decision"]["allowed"] is True
    assert data["trade_decision"]["reason"] == "trade_allowed"


def test_trade_not_authorized_without_device_right():
    resp = client.post("/market/recommend", json=_body(trade_enabled=False))
    assert resp.status_code == 200
    assert resp.json()["trade_decision"]["reason"] == "trade_not_authorized"


def test_trade_volume_limit_enforced(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_TRADE_LIMITS", "true")
    monkeypatch.setenv("AXIS_POLICY_TRADE_MAX_VOLUME_WH", "100")

    resp = client.post("/market/recommend", json=_body())
    data = resp.json()
    assert data["trade_decision"]["allowed"] is False
    assert data["trade_decision"]["reason"] == "trade_volume_exceeded"


def test_trade_dao_gate_enforced(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_TRADE_REQUIRES_DAO", "true")

    gated = client.post("/market/recommend", json=_body()).json()
    assert gated["trade_decision"]["reason"] == "trade_dao_gated"

    approved = client.post("/market/recommend", json=_body(dao_approved=True)).json()
    assert approved["trade_decision"]["allowed"] is True


def test_invalid_inputs_return_400():
    resp = client.post("/market/recommend", json=_body(capacity_wh=0.0))
    assert resp.status_code == 400
