"""Tests for the AI signal layer scaffold (Phase 0)."""

from axis_core.ai import Signal, SignalProvider


def test_provider_returns_neutral_noop():
    provider = SignalProvider()
    signal = provider.evaluate(device_id="dev_1")
    assert signal.level == "neutral"
    assert signal.kind == "none"
    assert signal.score == 0.0
    assert signal.is_anomaly is False
    assert signal.details["device_id"] == "dev_1"


def test_provider_signature_accepts_future_inputs():
    provider = SignalProvider()
    signal = provider.evaluate(
        device_id="dev_2",
        report={"verified": True, "kwh": 1.5},
        history=[{"month": "2026-08", "kwh": 30.0}],
        market={"prices": [{"price": 10.0, "ts": 0}]},
    )
    assert signal.level == "neutral"


def test_signal_shape():
    signal = Signal(level="anomaly", kind="ai_anomaly", score=0.92)
    assert signal.is_anomaly is True
    assert signal.kind == "ai_anomaly"
    assert signal.score == 0.92


def test_signal_anomaly_flag_only_for_anomaly_level():
    assert Signal(level="info", kind="forecast").is_anomaly is False
    assert Signal(level="warning", kind="market").is_anomaly is False
