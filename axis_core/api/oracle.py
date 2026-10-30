import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from jsonschema import ValidationError

from axis_core.ai import SignalProvider
from axis_core.config import mock_mode_enabled
from axis_core.oracle_keys import sign_attestation
from axis_core.policy.config import load_policy_config
from axis_core.policy.engine import PolicyEngine
from axis_core.policy.models import OracleReport, PolicyRegistry, ProducerState
from axis_core.schema_utils import validate_payload
from axis_core.storage.factory import get_backend
from axis_core.signature_utils import canonical_proof_message, verify_ed25519_signature
from axis_core.wire import TrustEnvelope, validate_envelope, verify_envelope

router = APIRouter(prefix="/oracle", tags=["oracle"])

ORACLE_ID = "oracle_main_1"


def _now_iso8601_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _epoch_to_iso8601_z(epoch: int) -> str:
    """Convert Unix epoch seconds to an ISO 8601 UTC string with a 'Z' suffix."""
    return (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


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


# ── Trust Envelope (wire-format §2, accepted on this endpoint since 2026-09-16) ──


def _is_trust_envelope(payload: Any) -> bool:
    """True when the request body is an L0 Trust Envelope instead of a bare proof."""
    return isinstance(payload, dict) and {
        "envelope_version",
        "message_header",
        "message_payload",
    }.issubset(payload.keys())


def _unwrap_trust_envelope(envelope_body: Dict[str, Any]) -> Dict[str, Any]:
    """Authenticate a Trust Envelope and return the device proof it carries.

    Wire-format §8 makes this a **MUST** before a message is accepted: structural
    validation, then ``issuer_id`` binding, then the Ed25519 signature over the
    ENTIRE envelope (envelope header + message header + payload). The issuer is
    checked against the key **on file for the device**, never against a key the
    sender supplies.

    Failures stay transport-level (they are not policy decisions):
    - **400** structural violation (unsupported ``envelope_version``, unknown
      ``message_type``, missing ``issuer_id``/``entity_id``, header/payload
      timestamp disagreement);
    - **401** authentication failure (unsigned envelope, bad signature, issuer is
      not the identity that signed);
    - **403** the claimed device is not registered (so no key to authenticate with).

    The returned proof still goes through the normal pipeline: the envelope proves
    *this hop* (who delivered the message), the inner signature proves *the device*.
    Neither replaces the other.
    """
    envelope = TrustEnvelope.from_dict(envelope_body)

    try:
        validate_envelope(envelope)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid Trust Envelope: {e}")

    if not envelope.signature:
        raise HTTPException(status_code=401, detail={"reason": "envelope_unsigned"})

    body = envelope.message_payload or {}
    device_id = body.get("device_id") or envelope.message_header.get("entity_id", "")
    device = get_backend().get_device(device_id)
    if device is None:
        raise HTTPException(status_code=403, detail={"reason": "device_not_registered"})

    if not verify_envelope(envelope, device.public_key):
        raise HTTPException(
            status_code=401, detail={"reason": "envelope_signature_invalid"}
        )

    # The proof body the DEVICE signed: `canonical_proof_message` covers
    # device_id, nonce, timestamp, algo, payload.
    header_ts = envelope.message_header.get("timestamp") or ""
    payload_ts = body.get("timestamp")

    header_epoch: Optional[int] = None
    if header_ts:
        try:
            _ensure_iso8601_z(header_ts)
            header_epoch = _timestamp_to_epoch(header_ts)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Trust Envelope: message_header.timestamp must be an "
                "ISO 8601 UTC timestamp with a 'Z' suffix",
            )

    payload_epoch: Optional[int] = None
    if payload_ts is not None:
        try:
            payload_epoch = int(payload_ts)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Trust Envelope: message_payload.timestamp must be an "
                "integer (Unix epoch seconds)",
            )

    if (
        header_epoch is not None
        and payload_epoch is not None
        and header_epoch != payload_epoch
    ):
        raise HTTPException(
            status_code=400,
            detail="Trust Envelope: message_header.timestamp disagrees with "
            "message_payload.timestamp",
        )

    timestamp = header_ts or (
        _epoch_to_iso8601_z(payload_epoch) if payload_epoch is not None else ""
    )
    return {
        "device_id": device_id,
        "nonce": body.get("nonce", ""),
        "timestamp": timestamp,
        "algo": "ed25519",
        "payload": body.get("event_data", {}),
        "signature": body.get("signature", ""),
    }


def _policy_config() -> PolicyRegistry:
    """The active policy set (env > policy config file > defaults).

    Reloaded on every call so runtime changes of ``AXIS_POLICY_*`` take effect
    without a restart — appropriate for the reference service.
    """
    return load_policy_config()


def _sterility_signal(payload: Dict[str, Any]) -> SimpleNamespace:
    """Statement #87's reading, shaped for ``PolicyEngine.evaluate_sterility``.

    The engine duck-types ``a2`` and ``cv``; everything else the payload carries
    (``verdict``, ``r0``, ``points``...) travels in ``details`` untouched, so a
    decision can quote the reading back without the engine knowing this layer.
    A payload without either number yields ``None``, and the gate then has
    nothing to refuse on.
    """
    details = {k: v for k, v in payload.items() if k not in {"a2", "cv"}}
    return SimpleNamespace(a2=payload.get("a2"), cv=payload.get("cv"), details=details)


def _ai_history(request: Dict[str, Any]) -> list:
    """Chronological history for the AI anomaly signal.

    Past attestations of the device (from the registry storage) plus the
    current report as the last element, so a spike is visible immediately.
    Only the fields the anomaly detector understands are kept (``nonce``,
    ``max_power_kw``; ``energy_wh`` arrives with the energy attestation API).
    """
    device_id = request["device_id"]
    history = []

    for att in get_backend().all_attestations().values():
        if att.get("device_id") != device_id:
            continue
        proof = att.get("proof") or {}
        entry: Dict[str, Any] = {}
        nonce = proof.get("nonce")
        if nonce is not None:
            try:
                entry["nonce"] = int(nonce)
            except (TypeError, ValueError):
                pass
        power = (proof.get("payload") or {}).get("max_power_kw")
        if power is not None:
            entry["max_power_kw"] = float(power)
        history.append(entry)

    # Current report goes last (it is not persisted yet at decision time).
    current: Dict[str, Any] = {}
    nonce = request.get("nonce")
    if nonce is not None:
        try:
            current["nonce"] = int(nonce)
        except (TypeError, ValueError):
            pass
    current["max_power_kw"] = float(request.get("payload", {}).get("max_power_kw", 0.0))
    history.append(current)

    history.sort(key=lambda e: e.get("nonce", 0))
    return history[-20:]


def _resolve_decision(request: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the oracle decision for an attestation request.

    Responsibilities are split per ADR-0003:

    **Verifier** (executor — cryptography and data transport):
      1. algorithm support (``ed25519`` required by default; ``mock`` is a
         documented dev-only mode);
      2. device registration (the registry is the source of truth, ed25519 only);
      3. Ed25519 signature verification against the registered public key;
      4. nonce replay protection (``nonce_replay``).

    **Policy Engine** (the single decision point — ``axis_core.policy``):
      5. timestamp freshness (``stale_timestamp`` / ``future_timestamp``),
         device state, tier/energy limits (configurable, defaults relaxed for
         the reference service — see ``axis_core.policy.config``);

    **Domain policy** (provisioning profile, ADR-0006):
      6. ``max_power_kw`` limit (``max_power_exceeded`` / ``below_minimum_power``).

    The decision dict always contains ``allowed``, ``reason`` and
    ``max_power_kw``; a ``limit_kw`` field is added for policy denials.
    """
    device_id = request["device_id"]
    algo = request.get("algo", "ed25519")
    max_power_kw = request.get("payload", {}).get("max_power_kw", 0.0)

    # ── Verifier (ADR-0003): cryptography and transport only ─────────────────
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

    # 3. Verify the device signature over the canonical message (ed25519).
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

    # 4. Nonce replay protection.
    nonce = request.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return _decision(False, "invalid_nonce", 0.0)
    if get_backend().has_nonce(device_id, nonce):
        return _decision(False, "nonce_replay", 0.0)
    get_backend().record_nonce(device_id, nonce)

    # ── Policy Engine (ADR-0003): every admissibility decision ───────────────
    try:
        ts_epoch = _timestamp_to_epoch(request["timestamp"])
    except (KeyError, TypeError, ValueError):
        return _decision(False, "invalid_timestamp", 0.0)
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    report = OracleReport(
        device_id=device_id,
        nonce=0,
        device_timestamp=ts_epoch,
        verified_at=ts_epoch,
        energy_wh=0,
    )
    policy = _policy_config()
    decision = PolicyEngine.evaluate_preamble(
        policy=policy,
        producer=ProducerState(device_id=device_id),
        report=report,
        now=now_epoch,
    )
    if not decision.allowed:
        return _decision(False, decision.reason, 0.0)

    # ── AI signals (ENRG-AI, Phase 1): opt-in off-chain gate ─────────────────
    # Constitution (ADR-0003): the AI oracle is a source of signals, not
    # decisions. Nothing runs here unless an operator/DAO enabled
    # ``enforce_ai_anomaly``; the anomaly then rejects the report with the
    # stable ``ai_anomaly_flagged`` reason.
    if policy.enforce_ai_anomaly:
        signal = SignalProvider(
            anomaly_threshold=policy.ai_anomaly_threshold
        ).evaluate(
            device_id=device_id,
            history=_ai_history(request),
        )
        ai_decision = PolicyEngine.evaluate_ai_anomaly(policy=policy, signal=signal)
        if not ai_decision.allowed:
            return _decision(False, ai_decision.reason, 0.0)

    # ── Collusion signal (Statement #87, ENRG-AI): opt-in off-chain gate ─────
    # The physics layer reads the sterility index off a device's relief trace
    # and ships it in the request payload as {"a2": ..., "cv": ...}. Nothing
    # runs unless an operator/DAO enabled ``enforce_sterility``; the gate then
    # blocks the mint with the stable ``synthetic_collusion_detected`` reason.
    if policy.enforce_sterility:
        sterility = (request.get("payload") or {}).get("sterility")
        if isinstance(sterility, dict):
            sterility_decision = PolicyEngine.evaluate_sterility(
                policy=policy, signal=_sterility_signal(sterility)
            )
            if not sterility_decision.allowed:
                return _decision(False, sterility_decision.reason, 0.0)

    # ── Domain policy (provisioning profile, ADR-0006): power limit ──────────
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

    Accepted bodies:

    0. **Trust Envelope** (`spec/protocol/wire-format.md` §2). The body is
       authenticated as a whole before any policy logic runs — structure, issuer
       binding, Ed25519 signature over the entire envelope (§8) — and the device
       proof it carries is then processed exactly like mode 2. See
       `_unwrap_trust_envelope` for the failure codes.
    1. Legacy: a full Attestation document. The embedded device proof is
       re-verified through the same decision pipeline (signature + policy) and
       the attestation is re-signed by the oracle. Unverifiable proofs are
       rejected with 403.
    2. New: an oracle_attest_request. The device Ed25519 signature is verified
       against the registered public key, freshness/replay are enforced, and
       the resulting attestation is signed by the oracle.
    """
    # Mode 0: L0 Trust Envelope (wire-format §2/§8).
    if _is_trust_envelope(payload):
        payload = _unwrap_trust_envelope(payload)

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
