from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from jsonschema import ValidationError

from app.services.provisioning_service import register_device, _DB
from app.schema_utils import get_validator


router = APIRouter()

DEVICE_PROOF_VALIDATOR = get_validator("device_proof")


class ProvisioningRequest(BaseModel):
    public_key: str
    manifest_ref: str | None = None
    proof: dict | None = None  # will be linked with JSON Schema later


class ProvisioningResponse(BaseModel):
    device_id: str
    manifest_ref: str
    bootstrap_policy: dict


@router.post("/register", response_model=ProvisioningResponse)
async def provisioning_register(req: ProvisioningRequest):
    try:
        result = register_device(req)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/attest")
async def provisioning_attest(proof: Dict[str, Any]):
    """
    Accepts DeviceProof, validates against JSON Schema, and returns a simple decision.
    """
    # Backwards-compatible: if client didn't send schema_version, assume "1.0"
    if "schema_version" not in proof:
        proof = {**proof, "schema_version": "1.0"}

    try:
        DEVICE_PROOF_VALIDATOR.validate(proof)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid DeviceProof",
                "error": e.message,
                "path": list(e.path),
            },
        )

    device_id = proof.get("device_id")
    if device_id not in _DB:
        # Special case: device not registered
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid DeviceProof",
                "path": ["device_id"],
            },
        )

    decision = {
        "allowed": True,
        "reason": "mock-allowed",
    }

    return {
        "status": "ok",
        "device_id": device_id,
        "decision": decision,
    }
