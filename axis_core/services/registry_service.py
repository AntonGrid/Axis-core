from typing import Dict, Optional

from axis_core.storage.factory import get_backend


def get_device_record(device_id: str) -> Optional[Dict]:
    dev = get_backend().get_device(device_id)
    if not dev:
        return None

    return {
        "device_id": dev.device_id,
        "public_key": dev.public_key,
        "owner": None,
        "lifecycle_state": "provisioned",
        "firmware_version": None,
        "manifest_ref": dev.manifest_ref,
    }

