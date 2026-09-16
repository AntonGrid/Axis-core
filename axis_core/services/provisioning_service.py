import hashlib
from typing import Dict

from axis_core.config import mock_mode_enabled
from axis_core.signature_utils import (
    canonical_registration_message,
    is_valid_public_key_b64,
    verify_ed25519_signature,
)
from axis_core.storage.factory import get_backend
from axis_core.storage.models import RegisteredDevice


def _generate_device_id(public_key: str) -> str:
    return "dev_" + hashlib.sha256(public_key.encode()).hexdigest()[:16]


def register_device(req) -> Dict:
    public_key = req.public_key
    if not public_key:
        raise ValueError("public_key is required")
    if not is_valid_public_key_b64(public_key):
        raise ValueError("public_key must be a Base64-encoded 32-byte Ed25519 key")

    # Proof of possession (ADR-0001): the device must prove it holds the
    # private key that corresponds to the public key it registers. In dev mode
    # (AXIS_ALLOW_MOCK=1) the signature may be omitted for tooling/tests.
    signature = req.signature
    nonce = req.nonce
    if not mock_mode_enabled():
        if not signature or not nonce:
            raise ValueError("signature and nonce are required (proof of possession)")
        message = canonical_registration_message(public_key, nonce)
        if not verify_ed25519_signature(public_key, message, signature):
            raise ValueError("invalid signature: proof of device key ownership required")

    device_id = _generate_device_id(public_key)
    manifest_ref = req.manifest_ref or "manifest:v0-placeholder"

    bootstrap_policy = {
        "allowed": True,
        "max_power_kw": 3.5,
    }

    get_backend().put_device(
        RegisteredDevice(
            device_id=device_id,
            public_key=public_key,
            manifest_ref=manifest_ref,
            bootstrap_policy=bootstrap_policy,
        )
    )

    return {
        "device_id": device_id,
        "manifest_ref": manifest_ref,
        "bootstrap_policy": bootstrap_policy,
    }


#: Provisioning-profile fallback power limit (kW) used when a device has no
#: ``bootstrap_policy.max_power_kw`` — mirrors the reference oracle's 5 kW domain
#: limit (ADR-0006).
DEFAULT_MAX_POWER_KW = 5.0

#: A proof below this power is not a meaningful device reading (mirrors the
#: reference oracle's rule for the documented dev-only ``mock`` algorithm).
MIN_POWER_KW = 0.1


def attest_device_proof(proof: Dict) -> Dict:
    """Decide whether a ``DeviceProof`` is admissible (ADR-0003).

    The Verifier (the API layer) has already validated the proof against
    ``device_proof.schema.json`` and checked that the device is registered — the
    DECISION belongs to the policy layer. This implements the **provisioning
    profile domain policy** (ADR-0006): the per-device ``bootstrap_policy`` that
    was recorded at registration, falling back to the reference limits above.

    Returns a decision dict with STABLE reason codes:

    - ``device_not_registered``            — the registry has no such device;
    - ``not_allowed_by_bootstrap_policy``  — the device is provisionally disabled;
    - ``max_power_exceeded``               — ``payload.max_power_kw`` above the limit;
    - ``below_minimum_power``              — ``mock`` algo below ``MIN_POWER_KW``;
    - ``ok``                               — admissible.

    The old implementation returned a hardcoded ``{"allowed": true, "reason":
    "mock-allowed"}`` — the reference implementation *pretending* to decide, which
    contradicted the repository's own conformance claims (audit 2026-09-16).
    """
    device_id = proof.get("device_id")
    device = get_backend().get_device(device_id) if device_id else None
    if device is None:
        return {"allowed": False, "reason": "device_not_registered"}

    bootstrap = device.bootstrap_policy or {}
    algo = proof.get("algo", "ed25519")
    payload = proof.get("payload") or {}
    try:
        max_power_kw = float(payload.get("max_power_kw", 0.0))
    except (TypeError, ValueError):
        return {"allowed": False, "reason": "invalid_max_power_kw"}

    if not bootstrap.get("allowed", True):
        return {"allowed": False, "reason": "not_allowed_by_bootstrap_policy"}

    try:
        limit_kw = float(bootstrap.get("max_power_kw", DEFAULT_MAX_POWER_KW))
    except (TypeError, ValueError):
        limit_kw = DEFAULT_MAX_POWER_KW

    if max_power_kw > limit_kw:
        return {
            "allowed": False,
            "reason": "max_power_exceeded",
            "max_power_kw": max_power_kw,
            "limit_kw": limit_kw,
        }

    if algo == "mock" and max_power_kw < MIN_POWER_KW:
        return {
            "allowed": False,
            "reason": "below_minimum_power",
            "max_power_kw": max_power_kw,
            "limit_kw": MIN_POWER_KW,
        }

    return {"allowed": True, "reason": "ok", "max_power_kw": max_power_kw}

