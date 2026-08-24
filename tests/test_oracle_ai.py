"""End-to-end AI anomaly gate tests through the oracle API (Phase 1).

A device submits a series of valid Ed25519-signed proofs with a steady
``max_power_kw``, then a sudden spike. With ``enforce_ai_anomaly`` disabled
(default) the spike is allowed (backward compatible); with it enabled the
oracle rejects the report with the stable ``ai_anomaly_flagged`` reason.
"""

from fastapi.testclient import TestClient

from axis_core.main import app

from tests.signature_helpers import build_signed_proof, make_registered_device, now_iso8601_z

client = TestClient(app)


def _submit(key, device_id, nonce, power_kw):
    proof = build_signed_proof(key, device_id, nonce, now_iso8601_z(), power_kw)
    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200, f"attest failed: {resp.text}"
    return resp.json()


def test_ai_anomaly_disabled_by_default_allows_spike():
    key, device_id = make_registered_device(client)

    for i in range(5):
        decision = _submit(key, device_id, str(100 + i), 0.5)["decision"]
        assert decision["allowed"] is True

    spike = _submit(key, device_id, "105", 4.9)["decision"]
    assert spike["allowed"] is True  # no behavioral change by default


def test_ai_anomaly_blocks_power_spike_when_enabled(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_AI_ANOMALY", "true")

    key, device_id = make_registered_device(client)

    # Steady baseline: 5 reports at 0.5 kW — all allowed.
    for i in range(5):
        decision = _submit(key, device_id, str(200 + i), 0.5)["decision"]
        assert decision["allowed"] is True

    # A 10x power spike: the AI anomaly gate rejects it.
    spike = _submit(key, device_id, "205", 4.9)["decision"]
    assert spike["allowed"] is False
    assert spike["reason"] == "ai_anomaly_flagged"


def test_ai_anomaly_clean_history_stays_allowed_when_enabled(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_AI_ANOMALY", "true")

    key, device_id = make_registered_device(client)

    for i in range(6):
        decision = _submit(key, device_id, str(300 + i), 2.0)["decision"]
        assert decision["allowed"] is True


def test_ai_anomaly_threshold_env_is_respected(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_AI_ANOMALY", "true")

    # Strict threshold: a nonce gap of 2 (anomaly score 0.4) is enough to flag.
    monkeypatch.setenv("AXIS_POLICY_AI_ANOMALY_THRESHOLD", "0.3")
    key, device_id = make_registered_device(client)
    for i in range(5):
        assert _submit(key, device_id, str(500 + i), 0.5)["decision"]["allowed"] is True
    gap = _submit(key, device_id, "506", 0.5)["decision"]  # nonce gap 2 → score 0.4
    assert gap["allowed"] is False
    assert gap["reason"] == "ai_anomaly_flagged"

    # Lenient threshold: the same nonce gap no longer flags.
    monkeypatch.setenv("AXIS_POLICY_AI_ANOMALY_THRESHOLD", "0.5")
    key2, device_id2 = make_registered_device(client)
    for i in range(5):
        assert _submit(key2, device_id2, str(600 + i), 0.5)["decision"]["allowed"] is True
    gap = _submit(key2, device_id2, "606", 0.5)["decision"]
    assert gap["allowed"] is True
