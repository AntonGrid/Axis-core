"""Anomaly detection tests (axis_core.ai.anomaly)."""

from axis_core.ai.anomaly import detect_anomaly


def _power_history(*powers):
    return [{"max_power_kw": p} for p in powers]


def _energy_history(*energies):
    return [{"energy_wh": e} for e in energies]


def _nonce_history(*nonces):
    return [{"nonce": n} for n in nonces]


def test_empty_history_is_neutral():
    result = detect_anomaly("dev_1", [])
    assert result.is_anomaly is False
    assert result.score == 0.0
    assert result.signals == []
    assert result.details["samples"] == 0


def test_steady_power_series_has_no_signals():
    result = detect_anomaly("dev_1", _power_history(2.0, 2.1, 1.9, 2.0, 2.0))
    assert result.is_anomaly is False
    assert result.signals == []


def test_power_spike_is_detected():
    result = detect_anomaly("dev_1", _power_history(0.5, 0.5, 0.5, 0.5, 4.9))
    assert result.is_anomaly is True
    assert "power_spike" in result.signals
    assert result.score == 1.0
    assert result.details["power_ratio_vs_median"] == 9.8


def test_energy_spike_is_detected():
    result = detect_anomaly("dev_1", _energy_history(10, 10, 10, 10, 100))
    assert result.is_anomaly is True
    assert "energy_spike" in result.signals


def test_energy_and_power_fields_are_independent():
    # Only 3 power samples (< minimum) but 4 energy samples: the energy spike
    # must still fire while the power check stays silent.
    history = [
        {"energy_wh": 10, "max_power_kw": 0.5},
        {"energy_wh": 10, "max_power_kw": 0.5},
        {"energy_wh": 10, "max_power_kw": 0.5},
        {"energy_wh": 10, "max_power_kw": 0.5},
        {"energy_wh": 100, "max_power_kw": 4.9},
    ]
    result = detect_anomaly("dev_1", history)
    assert "energy_spike" in result.signals
    assert "power_spike" in result.signals


def test_spike_requires_minimum_samples():
    result = detect_anomaly("dev_1", _power_history(0.5, 0.5, 4.9))
    assert result.is_anomaly is False
    assert "power_spike" not in result.signals


def test_nonce_gap_is_detected():
    result = detect_anomaly("dev_1", _nonce_history(1, 2, 3, 10))
    assert "nonce_gap" in result.signals
    assert result.details["nonce_gap"] == 7
    assert result.is_anomaly is True


def test_sequential_nonces_are_tolerated():
    # A single skipped nonce (gap == 1) is tolerated as a retry.
    result = detect_anomaly("dev_1", _nonce_history(1, 2, 3, 4))
    assert "nonce_gap" not in result.signals
    assert result.is_anomaly is False


def test_threshold_controls_is_anomaly():
    history = _power_history(0.5, 0.5, 0.5, 0.5, 1.0)  # ratio == 2.0 → score 1.0
    assert detect_anomaly("dev_1", history, threshold=0.5).is_anomaly is True
    assert detect_anomaly("dev_1", history, threshold=1.5).is_anomaly is False
