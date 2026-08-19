"""Conformance tests: implementation ↔ Axis Protocol specification.

These tests verify that the reference implementation (this repository) is
consistent with:

1. its own OpenAPI description (`openapi.yaml` ↔ actual FastAPI routes);
2. its JSON Schemas (`schemas/` canonical copies ↔ `axis_core/schemas/` runtime);
3. the protocol terminology (proof, attestation, decision, manifest, ...);
4. the published attestation examples (allowed and denied scenarios) — both as
   schema-valid documents and as live API flows.

The normative protocol specification lives in the Axis-protocol repository
(`spec/protocol/*`, ADRs). Where the implementation intentionally deviates or
adds deployment-specific constraints, the differences are documented in the
“Conformance” section of the README.
"""
import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from axis_core.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
client = TestClient(app)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_openapi_yaml_matches_routes():
    """The committed openapi.yaml must describe exactly the routes FastAPI exposes.

    `app.openapi()` is the authoritative source for the actual route set (in this
    FastAPI version, included routers are represented as _IncludedRouter objects,
    so filtering app.routes by APIRoute is not reliable).
    """
    with (BASE_DIR / "openapi.yaml").open("r", encoding="utf-8") as f:
        documented = set(yaml.safe_load(f)["paths"].keys())

    generated = set(app.openapi()["paths"].keys())
    assert documented == generated, (
        f"openapi.yaml paths differ from the FastAPI-generated spec.\n"
        f"  Missing from openapi.yaml: {sorted(generated - documented)}\n"
        f"  Not implemented: {sorted(documented - generated)}"
    )


# ---------------------------------------------------------------------------
# JSON Schemas
# ---------------------------------------------------------------------------

def test_canonical_and_runtime_schemas_identical():
    """schemas/ (canonical reference) and axis_core/schemas/ (runtime) in sync."""
    canonical = {p.name for p in (BASE_DIR / "schemas").glob("*.json")}
    runtime = {p.name for p in (BASE_DIR / "axis_core" / "schemas").glob("*.json")}
    assert canonical == runtime

    for name in canonical:
        left = (BASE_DIR / "schemas" / name).read_bytes()
        right = (BASE_DIR / "axis_core" / "schemas" / name).read_bytes()
        assert left == right, f"Schema {name} diverged between schemas/ and axis_core/schemas/"


def test_all_schemas_are_valid_json_and_draft7():
    for dirname in ("schemas", "axis_core/schemas"):
        for schema_path in (BASE_DIR / dirname).glob("*.json"):
            schema = load_json(schema_path)
            # Draft7Validator construction fails on structurally invalid schemas.
            Draft7Validator(schema)


# ---------------------------------------------------------------------------
# Protocol terminology alignment
# ---------------------------------------------------------------------------

def test_schema_terminology_matches_protocol_glossary():
    """Core glossary terms (proof, attestation, decision, manifest, registry)
    must be reflected in the canonical field names."""
    attestation = load_json(BASE_DIR / "schemas" / "attestation.schema.json")
    attestation_props = set(attestation["properties"].keys())
    assert {"attestation_id", "device_id", "proof", "decision", "oracle_id"} <= attestation_props

    decision_props = set(attestation["properties"]["decision"]["properties"].keys())
    assert {"allowed", "reason", "max_power_kw"} <= decision_props

    manifest = load_json(BASE_DIR / "schemas" / "device_manifest.schema.json")
    assert {"manifest_id", "version", "manufacturer", "model", "capabilities"} <= set(
        manifest["properties"].keys()
    )

    record = load_json(BASE_DIR / "schemas" / "device_record.schema.json")
    assert {"device_id", "public_key", "lifecycle_state", "manifest_ref"} <= set(
        record["properties"].keys()
    )

    proof = load_json(BASE_DIR / "schemas" / "device_proof.schema.json")
    assert {"device_id", "nonce", "timestamp", "signature"} <= set(proof["properties"].keys())


# ---------------------------------------------------------------------------
# Attestation examples → schema → API
# ---------------------------------------------------------------------------

def test_attestation_examples_validate_against_schema():
    schema = load_json(BASE_DIR / "axis_core" / "schemas" / "attestation.schema.json")
    validator = Draft7Validator(schema)

    for example_name in ("attestation-example.json", "attestation-example-deny.json"):
        example = load_json(BASE_DIR / example_name)
        errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
        assert not errors, (
            f"{example_name} does not match attestation.schema.json: "
            f"{[e.message for e in errors]}"
        )


def test_attestation_examples_through_oracle_api():
    for example_name in ("attestation-example.json", "attestation-example-deny.json"):
        example = load_json(BASE_DIR / example_name)

        resp = client.post("/oracle/attest", json=example)
        assert resp.status_code == 200, f"{example_name}: {resp.text}"
        body = resp.json()
        assert body["status"] == "received"
        assert body["attestation_id"] == example["attestation_id"]

        stored = client.get(f"/oracle/attestations/{example['attestation_id']}")
        assert stored.status_code == 200
        assert stored.json() == example, f"{example_name} was modified on storage"


def test_oracle_decision_allowed():
    resp = client.post(
        "/oracle/attest",
        json={
            "device_id": "dev_9e9c644e1580a83b",
            "nonce": "nonce_allowed_123456",
            "timestamp": "2026-07-25T19:05:00Z",
            "algo": "mock",
            "payload": {"max_power_kw": 2.5},
            "signature": "deadbeef" * 8,
        },
    )
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is True
    assert decision["reason"] == "ok"
    assert decision["max_power_kw"] == 2.5


def test_oracle_decision_denied_when_power_exceeds_limit():
    resp = client.post(
        "/oracle/attest",
        json={
            "device_id": "dev_deny_power_00000000",
            "nonce": "nonce_denied_123456",
            "timestamp": "2026-07-25T19:05:00Z",
            "algo": "mock",
            "payload": {"max_power_kw": 10.0},
            "signature": "deadbeef" * 8,
        },
    )
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["allowed"] is False
    assert decision["reason"] == "max_power_exceeded"
    assert decision["max_power_kw"] == 5.0
    assert decision["limit_kw"] == 5.0


# ---------------------------------------------------------------------------
# Provisioning → Registry end-to-end
# ---------------------------------------------------------------------------

def test_provisioning_register_attest_registry_flow():
    public_key = "conformance-test-public-key-0001"
    register = client.post("/provisioning/register", json={"public_key": public_key})
    assert register.status_code == 200
    device_id = register.json()["device_id"]
    assert device_id.startswith("dev_")

    attest = client.post(
        "/provisioning/attest",
        json={
            "schema_version": "1.0",
            "device_id": device_id,
            "nonce": "conformance_nonce_1234",
            "timestamp": "2026-07-25T19:00:00Z",
            "algo": "mock",
            "payload": {"max_power_kw": 2.5},
            "signature": "deadbeef" * 8,
        },
    )
    assert attest.status_code == 200
    assert attest.json()["decision"]["allowed"] is True

    record = client.get(f"/registry/devices/{device_id}")
    assert record.status_code == 200
    rec = record.json()
    assert rec["device_id"] == device_id
    assert rec["public_key"] == public_key
    assert rec["lifecycle_state"] == "provisioned"
