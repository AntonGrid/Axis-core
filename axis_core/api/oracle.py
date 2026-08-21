import os
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from jsonschema import ValidationError

from axis_core.config import MAX_CLOCK_SKEW_SECONDS, MAX_PROOF_AGE_SECONDS, mock_mode_enabled
from axis_core.oracle_keys import sign_attestation
from axis_core.schema_utils import validate_payload
from axis_core.storage.factory import get_backend
from axis_core.signature_utils import canonical_proof_message, verify_ed25519_signature

router = APIRouter(prefix="/oracle", tags=["oracle"])

ORACLE_ID = "oracle_main_1"


def _now_iso8601_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_iso8601_z(ts: str) -> None:
    """
    Checks that timestamp is in ISO 8601 UTC format with 'Z' suffix.
    Example: '2026-07-25T19:05:00Z'.
    """
    if not isinstance(ts, str):
        raise ValueError("timestamp must be a string")

    if not ts.endswith("Z"):
        raise ValueError("timestamp must end with 'Z'")

    _timestamp_to_epoch(ts)


def _timestamp_to_epoch(ts: str) -> int:
    """Convert an ISO 8601 UTC timestamp (with 'Z') to Unix epoch seconds."""
    iso = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _decision(
    allowed: bool,
    reason: str,
    max_power_kw: float,
    limit_kw: float | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "allowed": allowed,
        "reason": reason,
        "max_power_kw": max_power_kw,
    }
    if limit_kw is not None:
        result["limit_kw"] = limit_kw
    return result


def _sign_or_stub(attestation: Dict[str, Any]) -> str:
    """Sign the attestation with the oracle key, or stub it in mock mode.

    When ``ORACLE_SECRET_KEY`` is unset and mock mode is disabled, this raises
    ``HTTPException(503)`` so the oracle never emits an unsigned attestation.
    """
    secret_key_b64 = os.environ.get("ORACLE_SECRET_KEY", "").strip()
    if secret_key_b64:
        return sign_attestation(attestation, secret_key_b64)
    if mock_mode_enabled():
        return "mock-oracle-signature"
    raise HTTPException(
        status_code=503,
        detail="oracle key not configured: set ORACLE_SECRET_KEY "
        "(Base64-encoded 32-byte Ed25519 seed)",
    )


def _resolve_decision(request: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the oracle decision for an attestation request.

    Order of checks:
      1. algorithm support (``ed25519`` required by default; ``mock`` is a
         documented dev-only mode);
      2. device registration (the registry is the source of truth, ed25519 only);
      3. timestamp freshness (``stale_timestamp`` / ``future_timestamp``);
      4. Ed25519 signature verification against the registered public key;
      5. nonce replay protection (``nonce_replay``);
      6. mock Policy Engine rules on ``max_power_kw``.

    The decision dict always contains ``allowed``, ``reason`` and
    ``max_power_kw``; a ``limit_kw`` field is added for policy denials.
    """
    device_id = request["device_id"]
    algo = request.get("algo", "ed25519")
    max_power_kw = request.get("payload", {}).get("max_power_kw", 0.0)

    # 1. Algorithm support.
    if algo not in ("ed25519", "mock"):
        return _decision(False, "unsupported_algo", 0.0)
    if algo == "mock" and not mock_mode_enabled():
        return _decision(False, "mock_disabled", 0.0)

    # 2. The device MUST be registered (registry = source of truth).
    device = None
    if algo == "ed25519":
        device = get_backend().get_device(device_id)
        if device is None:
            return _decision(False, "device_not_registered", 0.0)

    # 3. Timestamp freshness (both algorithms).
    try:
        ts_epoch = _timestamp_to_epoch(request["timestamp"])
    except (KeyError, TypeError, ValueError):
        return _decision(False, "invalid_timestamp", 0.0)
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    if ts_epoch > now_epoch + MAX_CLOCK_SKEW_SECONDS:
        return _decision(False, "future_timestamp", 0.0)
    if now_epoch - ts_epoch > MAX_PROOF_AGE_SECONDS:
        return _decision(False, "stale_timestamp", 0.0)

    # 4. Verify the device signature over the canonical message (ed25519).
    if algo == "ed25519":
        try:
            signature_valid = verify_ed25519_signature(
                public_key_b64=device.public_key,
                message=canonical_proof_message(request),
                signature_b64=request.get("signature", ""),
            )
        except Exception:
            signature_valid = False
        if not signature_valid:
            return _decision(False, "signature_invalid", 0.0)

    # 5. Nonce replay protection.
    nonce = request.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return _decision(False, "invalid_nonce", 0.0)
    if get_backend().has_nonce(device_id, nonce):
        return _decision(False, "nonce_replay", 0.0)
    get_backend().record_nonce(device_id, nonce)

    # 6. Mock Policy Engine.
    if max_power_kw > 5.0:
        return _decision(False, "max_power_exceeded", 5.0, limit_kw=5.0)
    if algo == "mock" and max_power_kw < 0.1:
        return _decision(False, "below_minimum_power", 0.1, limit_kw=0.1)

    return _decision(True, "ok", max_power_kw)


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

    # Generate attestation
    att_id = str(uuid4())
    now = _now_iso8601_z()

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
        "oracle_id": ORACLE_ID,
        "issued_at": now,
    }

    attestation["oracle_signature"] = _sign_or_stub(attestation)
    return attestation


@router.post("/attest")
async def oracle_attest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Oracle attestation endpoint.

    Two modes:
    1. Legacy: a full Attestation document. The embedded device proof is
       re-verified through the same decision pipeline (signature + policy) and
       the attestation is re-signed by the oracle. Unverifiable proofs are
       rejected with 403.
    2. New: an oracle_attest_request. The device Ed25519 signature is verified
       against the registered public key, freshness/replay are enforced, and
       the resulting attestation is signed by the oracle.
    """
    # Mode 1: Legacy full Attestation document.
    if "attestation_id" in payload and "schema_version" in payload:
        try:
            validate_payload("attestation", payload)
            proof = payload.get("proof", {})
            _ensure_iso8601_z(proof.get("timestamp", ""))
            decision = _resolve_decision(proof)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Validation error: {e.message}")
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Validation error: {e!s}")

        if not decision["allowed"]:
            raise HTTPException(
                status_code=403,
                detail={"reason": decision["reason"]},
            )

        # Rebuild the attestation with the verified decision and a real oracle
        # signature so a client cannot inject `decision.allowed = true`.
        att_id = payload["attestation_id"]
        now = _now_iso8601_z()
        attestation = {
            "schema_version": "1.0",
            "attestation_id": att_id,
            "device_id": payload.get("device_id"),
            "proof": proof,
            "decision": decision,
            "oracle_id": payload.get("oracle_id", ORACLE_ID),
            "issued_at": now,
        }
        attestation["oracle_signature"] = _sign_or_stub(attestation)
        get_backend().put_attestation(att_id, attestation)

        return {
            "status": "received",
            "attestation_id": att_id,
            "device_id": payload.get("device_id"),
            "oracle_id": payload.get("oracle_id", ORACLE_ID),
        }

    # Mode 2: New oracle_attest_request
    try:
        validate_payload("oracle_attest_request", payload)

        # Validate timestamp format (freshness is checked in _resolve_decision).
        _ensure_iso8601_z(payload["timestamp"])

        # Build full attestation
        attestation = _build_attestation_from_request(payload)
        att_id = attestation["attestation_id"]

        # Store request and attestation
        request_id = str(uuid4())
        get_backend().put_request(request_id, {
            "request": payload,
            "attestation_id": att_id,
            "created_at": _now_iso8601_z(),
        })
        get_backend().put_attestation(att_id, attestation)

        return {
            "device_id": payload["device_id"],
            "attestation_id": att_id,
            "decision": attestation["decision"],
            "oracle_id": ORACLE_ID,
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
    atts = get_backend().all_attestations()
    keys = list(atts.keys())
    total = len(keys)
    paginated = keys[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "attestations": [
            {
                "attestation_id": key,
                "device_id": atts[key].get("device_id"),
                "issued_at": atts[key].get("issued_at"),
            }
            for key in paginated
        ],
    }


@router.get("/attestations/{attestation_id}")
async def get_attestation(attestation_id: str) -> Dict[str, Any]:
    """
    Get a specific attestation by ID.
    """
    att = get_backend().get_attestation(attestation_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attestation not found")
    return att


@router.get("/requests")
async def list_requests(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    List stored oracle requests.
    """
    reqs = get_backend().all_requests()
    keys = list(reqs.keys())
    total = len(keys)
    paginated = keys[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "requests": [
            {
                "request_id": key,
                "attestation_id": reqs[key].get("attestation_id"),
                "created_at": reqs[key].get("created_at"),
                "device_id": reqs[key].get("request", {}).get("device_id"),
            }
            for key in paginated
        ],
    }


@router.get("/requests/{request_id}")
async def get_request(request_id: str) -> Dict[str, Any]:
    """
    Get a specific oracle request by ID.
    """
    req = get_backend().get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req
