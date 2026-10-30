"""End-to-end sterility gate tests through the oracle API (Statement #87).

A device submits a signed proof whose payload carries a relief reading
``{"a2": ..., "cv": ...}``. With ``enforce_sterility`` disabled (default) the
reading is ignored and the mint proceeds — backward compatible. With it enabled
the oracle blocks a reading whose Anderson–Darling ``A²`` or ``CV(relief)`` is
below the policy floor, with the stable ``synthetic_collusion_detected`` reason.

The numbers are the ones ``consistency.jl`` produces: a lived relief reads
``A² = 8.204, CV = 0.175`` (seed 1), a formula reads ``A² = 0``.
"""

from fastapi.testclient import TestClient

from axis_core.main import app

from tests.signature_helpers import build_signed_proof, make_registered_device, now_iso8601_z

client = TestClient(app)

STERILE = {"a2": 0.0, "cv": 0.175, "verdict": "failed"}     # too exact to be lived
LIVED = {"a2": 8.204, "cv": 0.175, "verdict": "passed"}     # what a medium reads


def _submit(key, device_id, nonce, sterility=None):
    extra = {"sterility": sterility} if sterility is not None else None
    proof = build_signed_proof(
        key, device_id, nonce, now_iso8601_z(), 0.5, extra_payload=extra
    )
    resp = client.post("/oracle/attest", json=proof)
    assert resp.status_code == 200, f"attest failed: {resp.text}"
    return resp.json()["decision"]


def test_sterility_disabled_by_default_allows_too_perfect_relief():
    key, device_id = make_registered_device(client)
    decision = _submit(key, device_id, "900", STERILE)
    assert decision["allowed"] is True


def test_sterility_blocks_too_perfect_relief_when_enabled(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_STERILITY", "true")

    key, device_id = make_registered_device(client)
    decision = _submit(key, device_id, "910", STERILE)
    assert decision["allowed"] is False
    assert decision["reason"] == "synthetic_collusion_detected"


def test_sterility_passes_lived_relief_when_enabled(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_STERILITY", "true")

    key, device_id = make_registered_device(client)
    decision = _submit(key, device_id, "920", LIVED)
    assert decision["allowed"] is True


def test_sterility_absent_reading_never_blocks(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_STERILITY", "true")

    key, device_id = make_registered_device(client)
    decision = _submit(key, device_id, "930")
    assert decision["allowed"] is True


def test_sterility_threshold_env_is_respected(monkeypatch):
    monkeypatch.setenv("AXIS_POLICY_ENFORCE_STERILITY", "true")

    # A lived reading is blocked only if the operator raises the floor above it.
    monkeypatch.setenv("AXIS_POLICY_STERILITY_A2_THRESHOLD", "0.5")
    key, device_id = make_registered_device(client)
    assert _submit(key, device_id, "940", LIVED)["allowed"] is True

    monkeypatch.setenv("AXIS_POLICY_STERILITY_A2_THRESHOLD", "10.0")
    key2, device_id2 = make_registered_device(client)
    strict = _submit(key2, device_id2, "950", LIVED)
    assert strict["allowed"] is False
    assert strict["reason"] == "synthetic_collusion_detected"
