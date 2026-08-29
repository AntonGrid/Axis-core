"""Axis + Logistics profile — proof that the trust standard is domain-agnostic.

A cold-chain tracker (same trust pipeline as an energy meter, different
payload) signs temperature + location events; the oracle verifies the Ed25519
signature and applies a *domain* policy (cold-chain range 2..8 °C), then runs
the shared anomaly detector. Nothing in the core changes — the payload is
just a different JSON object.

Run:  python examples/logistics_profile.py
"""
from __future__ import annotations

import base64
import datetime as dt
import random
from typing import Any, Dict

from axis_core.ai.anomaly import detect_anomaly
from axis_core.signature_utils import (
    canonical_proof_message,
    encode_public_key,
    generate_device_key,
    sign_proof,
    verify_ed25519_signature,
)

#: Cold-chain domain policy: temperature must stay within 2..8 °C.
COLD_CHAIN_MIN_C = 2.0
COLD_CHAIN_MAX_C = 8.0


def build_proof(
    secret_key,
    *,
    nonce: int,
    temperature_c: float,
    location: str,
    timestamp: str,
) -> Dict[str, Any]:
    """One cold-chain event in the Axis proof shape (domain-agnostic payload)."""
    proof: Dict[str, Any] = {
        "algo": "ed25519",
        "device_id": encode_public_key(secret_key),
        "nonce": str(nonce),
        "timestamp": timestamp,
        "payload": {
            "temperature_c": round(temperature_c, 2),
            "location": location,
            "asset": "pharma_plx-01",
        },
    }
    proof["signature"] = sign_proof(secret_key, proof)
    return proof


def evaluate_cold_chain(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Domain policy: reject temperature outside the certified range."""
    temperature_c = float(payload.get("temperature_c", 0.0))
    if temperature_c < COLD_CHAIN_MIN_C or temperature_c > COLD_CHAIN_MAX_C:
        return {
            "allowed": False,
            "reason": "temperature_out_of_range",
            "temperature_c": temperature_c,
        }
    return {"allowed": True, "reason": "ok", "temperature_c": temperature_c}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    print("Axis + Logistics profile — cold-chain tracker (domain-agnostic demo)")
    print("=" * 70)

    secret_key = generate_device_key()
    public_key_b64 = encode_public_key(secret_key)
    print(f"tracker key   : {public_key_b64[:20]}…")
    print()

    # Honest tracker: 3 in-range events + 1 temperature excursion.
    events = [
        {"nonce": 1, "temperature_c": 4.0, "location": "RIGA-WH-01"},
        {"nonce": 2, "temperature_c": 5.5, "location": "RIGA-WH-01"},
        {"nonce": 3, "temperature_c": 6.2, "location": "LEG-01"},
        {"nonce": 4, "temperature_c": 13.4, "location": "LEG-01"},  # breach!
    ]

    history: list[Dict[str, Any]] = []
    for event in events:
        proof = build_proof(
            secret_key,
            nonce=event["nonce"],
            temperature_c=event["temperature_c"],
            location=event["location"],
            timestamp=now_iso(),
        )

        # 1. Cryptographic verification (shared core).
        message = canonical_proof_message(proof)
        sig_ok = verify_ed25519_signature(
            public_key_b64, message, proof["signature"]
        )

        # 2. Domain policy (profile-level).
        decision = evaluate_cold_chain(proof["payload"])

        # 3. Shared anomaly detector over the event history.
        anomaly = detect_anomaly(public_key_b64, history)

        status = "✅ attestation" if (sig_ok and decision["allowed"]) else "⛔ denied"
        reason = decision["reason"] if not decision["allowed"] else "ok"
        if anomaly.is_anomaly:
            reason = f"{reason} + anomaly({','.join(anomaly.signals)})"

        print(
            f"event #{event['nonce']}  {event['temperature_c']:>5.1f} °C "
            f"@{event['location']:<12} sig={'✓' if sig_ok else '✗'} "
            f"{status:<20} reason={reason}"
        )

        # The breach is recorded in history for anomaly detection next round.
        history.append(
            {
                "nonce": event["nonce"],
                "energy_wh": None,
                "max_power_kw": event["temperature_c"],
            }
        )

    print()
    print("The *same* Axis Core verifies, gates and flags — the payload is the")
    print("only difference from the energy profile (ENRG). Domain-agnostic ✓")


if __name__ == "__main__":
    main()
