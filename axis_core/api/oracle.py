import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from jsonschema import ValidationError

from axis_core.schema_utils import validate_payload
from axis_core.oracle_storage import _ATTESTATIONS, _REQUESTS
from axis_core.services.provisioning_service import _DB
from axis_core.signature_utils import canonical_proof_message, verify_ed25519_signature

router = APIRouter(prefix="/oracle", tags=["oracle"])


def _ensure_iso8601_z(ts: str) -> None:
    """
    Checks that timestamp is in ISO 8601 UTC format with 'Z' suffix.
    Example: '2026-07-25T19:05:00Z'.
    """
    if not isinstance(ts, str):
        raise ValueError("timestamp must be a string")

    if not ts.endswith("Z"):
        raise ValueError("timestamp must end with 'Z'")

    iso = ts[:-1] + "+00:00"
    try:
        datetime.fromisoformat(iso)
    except ValueError as e:
        raise ValueError(f"Invalid ISO 8601 timestamp: {e!s}") from e


def _mock_signatures_enabled() -> bool:
    """Whether the dev-only ``mock`` algorithm is accepted.

    Enabled via the ``AXIS_ALLOW_MOCK`` environment variable (``1``/``true``/``yes``).
    By default the oracle REQUIRES real ``ed25519`` signatures.
    """
    return os.environ.get("AXIS_ALLOW_MOCK", "").strip().lower() in {"1", "true", "yes"}


def _resolve_decision(request: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the oracle decision for an attestation request.

    Order of checks:
      1. algorithm support (``ed25519`` required by default; ``mock`` is a
         documented dev-only mode);
      2. device registration (the registry is the source of truth);
      3. Ed25519 signature verification against the registered public key;
      4. mock Policy Engine rules on ``max_power_kw``.

    The decision dict always contains ``allowed``, ``reason`` and
    ``max_power_kw``; a ``limit_kw`` field is added for policy denials.
    """
    device_id = request["device_id"]
    algo = request.get("algo", "ed25519")
    max_power_kw = request.get("payload", {}).get("max_power_kw", 0.0)

    # 1. Algorithm support
    if algo == "ed25519":
        # 2. The device MUST be registered (registry = source of truth).
        device = _DB.get(device_id)
        if device is None:
            return {
                "allowed": False,
                "reason": "device_not_registered",
                "max_power_kw": 0.0,
            }

        # 3. Verify the device signature over the canonical message.
        try:
            signature_valid = verify_ed25519_signature(
                public_key_b64=device.public_key,
                message=canonical_proof_message(request),
                signature_b64=request.get("signature", ""),
            )
        except Exception:
            signature_valid = False

        if not signature_valid:
            return {
                "allowed": False,
                "reason": "signature_invalid",
                "max_power_kw": 0.0,
            }
    elif algo == "mock":
        if not _mock_signatures_enabled():
            return {
                "allowed": False,
                "reason": "mock_disabled",
                "max_power_kw": 0.0,
            }
    else:
        return {
            "allowed": False,
            "reason": "unsupported_algo",
            "max_power_kw": 0.0,
        }

    # 4. Mock Policy Engine
    if max_power_kw > 5.0:
        return {
            "allowed": False,
            "reason": "max_power_exceeded",
            "max_power_kw": 5.0,
            "limit_kw": 5.0,
        }

    if algo == "mock" and max_power_kw < 0.1:
        return {
            "allowed": False,
            "reason": "below_minimum_power",
            "max_power_kw": 0.1,
            "limit_kw": 0.1,
        }

    return {
        "allowed": True,
        "reason": "ok",
        "max_power_kw": max_power_kw,
    }


def _build_attestation_from_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a full Attestation from an oracle_attest_request.
    """
    device_id = request["device_id"]
    nonce = request.get("nonce")
    timestamp = request.get("timestamp")
    algo = request.get("algo", "ed25519")
    max_power_kw = request.get("payload", {}).get("max_power_kw", 0.0)
    signature = request.get("signature")

    decision = _resolve_decision(request)
    allowed = decision["allowed"]
    limit_kw = decision.get("limit_kw")

    # Generate attestation
    att_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    attestation = {
        "schema_version": "1.0",
        "attestation_id": att_id,
        "device_id": device_id,
        "proof": {
            "device_id": device_id,
            "nonce": nonce or att_id[:8],
            "timestamp": timestamp or now,
            "algo": algo,
            "payload": {"max_power_kw": max_power_kw},
            "signature": signature or "mock-signature",
        },
        "decision": decision,
        "oracle_id": "oracle_main_1",
        "issued_at": now,
        "oracle_signature": "mock-oracle-signature",
    }

    if not allowed and limit_kw is not None:
        attestation["decision"]["limit_kw"] = limit_kw

    return attestation


@router.post("/attest")
async def oracle_attest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Oracle attestation endpoint.
    Two modes:
    1. Legacy: full Attestation JSON (schema_version: "1.0")
    2. New: oracle_attest_request (device_id, nonce, timestamp, algo, payload, signature)
    """
    # Mode 1: Legacy Attestation
    if "attestation_id" in payload and "schema_version" in payload:
        try:
            validate_payload("attestation", payload)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Validation error: {e.message}")

        att_id = payload["attestation_id"]
        _ATTESTATIONS[att_id] = payload

        return {
            "status": "received",
            "attestation_id": att_id,
            "device_id": payload.get("device_id"),
            "oracle_id": payload.get("oracle_id"),
        }

    # Mode 2: New oracle_attest_request
    try:
        validate_payload("oracle_attest_request", payload)

        # Validate timestamp if present
        if "timestamp" in payload:
            _ensure_iso8601_z(payload["timestamp"])

        # Build full attestation
        attestation = _build_attestation_from_request(payload)
        att_id = attestation["attestation_id"]

        # Store request and attestation
        request_id = str(uuid4())
        _REQUESTS[request_id] = {
            "request": payload,
            "attestation_id": att_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        _ATTESTATIONS[att_id] = attestation

        return {
            "device_id": payload["device_id"],
            "attestation_id": att_id,
            "decision": attestation["decision"],
            "oracle_id": "oracle_main_1",
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e.message}")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {e!s}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/attestations")
async def list_attestations(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    List stored attestations with pagination.
    """
    keys = list(_ATTESTATIONS.keys())
    total = len(keys)
    paginated = keys[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "attestations": [
            {
                "attestation_id": key,
                "device_id": _ATTESTATIONS[key].get("device_id"),
                "issued_at": _ATTESTATIONS[key].get("issued_at"),
            }
            for key in paginated
        ],
    }


@router.get("/attestations/{attestation_id}")
async def get_attestation(attestation_id: str) -> Dict[str, Any]:
    """
    Get a specific attestation by ID.
    """
    att = _ATTESTATIONS.get(attestation_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attestation not found")
    return att


@router.get("/requests")
async def list_requests(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    List stored oracle requests.
    """
    keys = list(_REQUESTS.keys())
    total = len(keys)
    paginated = keys[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "requests": [
            {
                "request_id": key,
                "attestation_id": _REQUESTS[key].get("attestation_id"),
                "created_at": _REQUESTS[key].get("created_at"),
                "device_id": _REQUESTS[key].get("request", {}).get("device_id"),
            }
            for key in paginated
        ],
    }


@router.get("/requests/{request_id}")
async def get_request(request_id: str) -> Dict[str, Any]:
    """
    Get a specific oracle request by ID.
    """
    req = _REQUESTS.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req
