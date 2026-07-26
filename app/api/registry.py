from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.registry_service import get_device_record

router = APIRouter()


class DeviceRecord(BaseModel):
    device_id: str
    public_key: str
    owner: str | None = None
    lifecycle_state: str
    firmware_version: str | None = None
    manifest_ref: str


@router.get("/devices/{device_id}", response_model=DeviceRecord)
async def registry_get_device(device_id: str):
    record = get_device_record(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")
    return record
