from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.provisioning_service import register_device

router = APIRouter()


class ProvisioningRequest(BaseModel):
    public_key: str
    manifest_ref: str | None = None
    proof: dict | None = None  # потом свяжем с JSON Schema


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
