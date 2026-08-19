import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# Add the repository root to sys.path so axis_core.* can be imported.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from axis_core.onchain_bridge import build_attestation_params  # noqa: E402


@dataclass
class AxisClient:
    """Minimal HTTP client for the /health and /oracle/attest endpoints."""

    base_url: str = "http://localhost:8000"

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def health(self) -> Dict[str, Any]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def oracle_attest_request(
        self,
        device_id: str,
        nonce: str,
        max_power_kw: float,
        algo: str = "mock",
        signature: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        if timestamp is None:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            timestamp = now.isoformat().replace("+00:00", "Z")
        if signature is None:
            signature = "deadbeef" * 8

        payload: Dict[str, Any] = {
            "device_id": device_id,
            "nonce": nonce,
            "timestamp": timestamp,
            "algo": algo,
            "payload": {"max_power_kw": max_power_kw},
            "signature": signature,
        }
        resp = self._client.post("/oracle/attest", json=payload)
        resp.raise_for_status()
        return resp.json()


def build_full_attestation_from_oracle_response(resp: dict) -> dict:
    """
    Convert the /oracle/attest response (new format) into a full Attestation
    compatible with attestation.schema.json and demo_onchain_bridge.
    """
    device_id = resp["device_id"]
    attestation_id = resp["attestation_id"]
    decision = resp["decision"]

    now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = now.isoformat().replace("+00:00", "Z")

    # Simulate the original proof request based on the decision
    proof = {
        "device_id": device_id,
        "nonce": "demo_nonce_123",
        "timestamp": issued_at,
        "algo": "mock",
        "payload": {
            "max_power_kw": decision.get("max_power_kw"),
        },
        "signature": "deadbeef" * 8,
    }

    full_attestation = {
        "schema_version": "1.0",  # explicitly set the schema version
        "attestation_id": attestation_id,
        "device_id": device_id,
        "proof": proof,
        "decision": {
            "allowed": bool(decision.get("allowed", True)),
            "reason": "auto-generated-from-oracle-response",
            "max_power_kw": decision.get("max_power_kw"),
        },
        "oracle_id": "oracle_main_1",
        "issued_at": issued_at,
        "oracle_signature": "cafebabe" * 8,
    }
    return full_attestation


def main():
    client = AxisClient()


    print("=== Step 1: /health ===")
    print(client.health())

    print("\n=== Step 2: POST /oracle/attest (new format) ===")
    oracle_resp = client.oracle_attest_request(
        device_id="dev_demo_full_cycle",
        nonce="nonce_full_cycle_123",
        max_power_kw=3.3,
    )
    print(json.dumps(oracle_resp, indent=2))

    print("\n=== Step 3: Build full Attestation from oracle response ===")
    full_att = build_full_attestation_from_oracle_response(oracle_resp)
    print(json.dumps(full_att, indent=2))

    print("\n=== Step 4: Build on-chain params via build_attestation_params ===")
    params = build_attestation_params(full_att)

    print("On-chain parameters for submitAttestation:")
    print(f"  attestationId (bytes32): 0x{params.attestation_id.hex()}")
    print(f"  deviceId      (bytes32): 0x{params.device_id.hex()}")
    print(f"  allowed       (bool)   : {params.allowed}")
    print(f"  maxPowerW     (uint64) : {params.max_power_w}")
    print(f"  issuedAt      (uint64) : {params.issued_at}")


if __name__ == "__main__":
    main()
