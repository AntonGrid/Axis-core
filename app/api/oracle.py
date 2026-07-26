from fastapi import APIRouter, HTTPException
from jsonschema import ValidationError

from app.schema_utils import get_validator


router = APIRouter(prefix="/oracle", tags=["oracle"])

ATT_VALIDATOR = get_validator("attestation")


@router.post("/attest")
def oracle_attest(attestation: dict):
    """
    Mock Oracle endpoint: принимает Attestation, валидирует по схеме и возвращает простое подтверждение.
    """
    try:
        ATT_VALIDATOR.validate(attestation)
    except ValidationError as e:
        path = list(e.path)
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid Attestation",
                "error": e.message,
                "path": path,
            },
        )

    return {
        "status": "received",
        "attestation_id": attestation["attestation_id"],
        "device_id": attestation["device_id"],
        "oracle_id": attestation["oracle_id"],
    }
