"""Shared data model for the storage layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class RegisteredDevice:
    device_id: str
    public_key: str
    manifest_ref: str
    bootstrap_policy: Dict


def device_to_dict(device: RegisteredDevice) -> dict:
    """Serialize a ``RegisteredDevice`` for JSON-based backends."""
    return {
        "device_id": device.device_id,
        "public_key": device.public_key,
        "manifest_ref": device.manifest_ref,
        "bootstrap_policy": device.bootstrap_policy,
    }


def device_from_dict(data: dict) -> RegisteredDevice:
    """Deserialize a ``RegisteredDevice`` from a JSON-ish mapping."""
    return RegisteredDevice(
        device_id=data["device_id"],
        public_key=data["public_key"],
        manifest_ref=data["manifest_ref"],
        bootstrap_policy=data["bootstrap_policy"],
    )
