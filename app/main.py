from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import secrets
from datetime import datetime, timezone

from jsonschema import Draft7Validator, ValidationError


app = FastAPI(title="ENRG Part II Mock with JSON Schema")

# --- JSON Schema loading and validators ---


BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = BASE_DIR / "schemas"


def load_schema(name: str) -> Dict[str, Any]:
    path = SCHEMAS_DIR / name
    if not path.exists():
        raise RuntimeError(f"Schema file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


device_manifest_schema = load_schema("device_manifest.schema.json")
device_record_schema = load_schema("device_record.schema.json")
device_proof_schema = load_schema("device_proof.schema.json")

device_manifest_validator = Draft7Validator(device_manifest_schema)
device_record_validator = Draft7Validator(device_record_schema)
device_proof_validator = Draft7Validator(device_proof_schema)

# --- In-memory registry (mock Device Registry) ---


DEVICE_REGISTRY: Dict[str, Dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Pydantic models for request bodies ---


class RegisterRequest(BaseModel):
    public_key: str


class DeviceProofRequest(BaseModel):
    # минимальная обертка, основная валидация — через JSON Schema
    device_id: str
    nonce: str
    timestamp: str
    algo: str
    payload: Dict[str, Any]
    signature: str


# --- Routes ---


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/provisioning/register")
def provisioning_register(body: RegisterRequest) -> Dict[str, Any]:
    """
    Minimal provisioning endpoint:
    - takes public_key
    - creates DeviceRecord (validated by JSON Schema)
    - returns device_id, manifest_ref and bootstrap_policy
    """

    # generate device_id (deterministic позже, сейчас псевдослучайный mock)
    random_suffix = secrets.token_hex(8)  # 16 hex chars
    device_id = f"dev_{random_suffix}"

    manifest_ref = "manifest:v0-placeholder"

    device_record: Dict[str, Any] = {
        "device_id": device_id,
        "public_key": body.public_key,
        "owner": None,
        "lifecycle_state": "provisioned",
        "firmware_version": None,
        "manifest_ref": manifest_ref,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "labels": {}
    }

    # Validate DeviceRecord against JSON Schema
    errors = sorted(device_record_validator.iter_errors(device_record), key=lambda e: e.path)
    if errors:
        # Это внутренняя ошибка сервиса, а не клиента, т.к. мы сами генерируем запись
        first = errors[0]
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Generated DeviceRecord does not conform to schema",
                "error": first.message,
                "path": list(first.path)
            },
        )

    # Save to in-memory registry
    DEVICE_REGISTRY[device_id] = device_record

    bootstrap_policy = {
        "allowed": True,
        "max_power_kw": 3.5
    }

    return {
        "device_id": device_id,
        "manifest_ref": manifest_ref,
        "bootstrap_policy": bootstrap_policy
    }


@app.get("/registry/devices/{device_id}")
def get_device(device_id: str) -> Dict[str, Any]:
    record = DEVICE_REGISTRY.get(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")

    # Optional: validate before returning (защита от случайной порчи в памяти)
    errors = sorted(device_record_validator.iter_errors(record), key=lambda e: e.path)
    if errors:
        first = errors[0]
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Stored DeviceRecord does not conform to schema",
                "error": first.message,
                "path": list(first.path)
            },
        )

    return record


@app.post("/provisioning/attest")
def provisioning_attest(body: DeviceProofRequest) -> Dict[str, Any]:
    """
    Device attestation endpoint (mock):
    - validates DeviceProof payload against JSON Schema
    - in реальном мире: передаём в Policy Engine, получаем решение и пр.
    """

    proof_dict = {
        "device_id": body.device_id,
        "nonce": body.nonce,
        "timestamp": body.timestamp,
        "algo": body.algo,
        "payload": body.payload,
        "signature": body.signature
    }

    errors = sorted(device_proof_validator.iter_errors(proof_dict), key=lambda e: e.path)
    if errors:
        first = errors[0]
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid DeviceProof",
                "error": first.message,
                "path": list(first.path)
            },
        )

    # Простая заглушка «Policy Engine»
    decision = {
        "allowed": True,
        "reason": "mock-allowed",
        "max_power_kw": proof_dict.get("payload", {}).get("max_power_kw", 3.5)
    }

    return {
        "status": "ok",
        "device_id": body.device_id,
        "decision": decision
    }
