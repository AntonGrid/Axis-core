"""Forecast tests (axis_core.ai.forecast)."""

from axis_core.ai.forecast import forecast_production


def _energy_history(*energies):
    return [{"energy_wh": e} for e in energies]


def test_linear_trend_is_projected():
    result = forecast_production("dev_1", _energy_history(10, 20, 30))
    assert result.forecast_wh == 40.0
    assert result.details["trend"] == "up"
    assert result.samples == 3


def test_flat_series_stays_flat():
    result = forecast_production("dev_1", _energy_history(10, 10, 10, 10))
    assert result.forecast_wh == 10.0
    assert result.details["trend"] == "flat"


def test_decreasing_series_never_goes_negative():
    result = forecast_production("dev_1", _energy_history(100, 50, 0))
    assert result.forecast_wh == 0.0
    assert result.details["trend"] == "down"


def test_not_enough_samples_returns_neutral():
    empty = forecast_production("dev_1", [])
    assert empty.forecast_wh is None
    assert empty.samples == 0

    single = forecast_production("dev_1", _energy_history(10))
    assert single.forecast_wh is None
    assert single.details["reason"] == "not enough samples"


def test_horizon_h_is_forwarded():
    result = forecast_production("dev_1", _energy_history(10, 20, 30), horizon_h=48)
    assert result.horizon_h == 48
