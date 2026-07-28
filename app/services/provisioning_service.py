from dataclasses import dataclass
from typing import Dict

from jsonschema import validate, ValidationError  # not used yet, but reserved


@dataclass
class RegisteredDevice:
    device_id: str
    public_key: str
    manifest_ref: str
    bootstrap_policy: Dict


_DB: Dict[str, RegisteredDevice] = {}


def _generate_device_id(public_key: str) -> str:
    import hashlib
    return "dev_" + hashlib.sha256(public_key.encode()).hexdigest()[:16]


def register_device(req) -> Dict:
    if not req.public_key:
        raise ValueError("public_key is required")

    device_id = _generate_device_id(req.public_key)
    manifest_ref = req.manifest_ref or "manifest:v0-placeholder"

    bootstrap_policy = {
        "allowed": True,
        "max_power_kw": 3.5,
    }

    _DB[device_id] = RegisteredDevice(
        device_id=device_id,
        public_key=req.public_key,
        manifest_ref=manifest_ref,
        bootstrap_policy=bootstrap_policy,
    )

    return {
        "device_id": device_id,
        "manifest_ref": manifest_ref,
        "bootstrap_policy": bootstrap_policy,
    }
