from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from jsonschema import ValidationError

from axis_core.services.provisioning_service import attest_device_proof, register_device
from axis_core.storage.factory import get_backend
from axis_core.schema_utils import get_validator


router = APIRouter()

DEVICE_PROOF_VALIDATOR = get_validator("device_proof")


class ProvisioningRequest(BaseModel):
    public_key: str
    manifest_ref: str | None = None
    signature: str | None = None
    nonce: str | None = None
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
    if get_backend().get_device(device_id) is None:
        # Special case: device not registered — the proof is not "denied by policy",
        # it is not admissible at all, so the documented 400 is kept.
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid DeviceProof",
                "path": ["device_id"],
            },
        )

    # ADR-0003: the decision belongs to the policy layer, not to the transport layer.
    # ADR-0006: the provisioning profile applies the device's bootstrap policy
    # (limits recorded at registration), returning stable reason codes.
    decision = attest_device_proof(proof)

    return {
        "status": "ok",
        "device_id": device_id,
        "decision": decision,
    }
