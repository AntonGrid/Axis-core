import json
import sys
from pathlib import Path

from eth_abi import encode as abi_encode
from eth_utils import keccak, to_hex

# Добавляем корень репозитория в sys.path, чтобы можно было импортировать app.* и tools.*
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.onchain_bridge import build_attestation_params  # noqa: E402
from tools.client import ENRGClient  # noqa: E402
from scripts.full_oracle_onchain_demo import (  # noqa: E402
    build_full_attestation_from_oracle_response,
)


def build_submit_attestation_calldata(params) -> str:
    """
    Строит calldata для Solidity-функции вида:

    function submitAttestation(
        bytes32 attestationId,
        bytes32 deviceId,
        bool allowed,
        uint64 maxPowerW,
        uint64 issuedAt
    ) external;

    Возвращает hex-строку вида 0x<4байта селектора><abi-кодированные аргументы>.
    """
    # Сигнатура функции
    signature = "submitAttestation(bytes32,bytes32,bool,uint64,uint64)"
    selector = keccak(text=signature)[:4]

    # ABI-кодирование аргументов
    encoded_args = abi_encode(
        ["bytes32", "bytes32", "bool", "uint64", "uint64"],
        [
            params.attestation_id,
            params.device_id,
            params.allowed,
            params.max_power_w,
            params.issued_at,
        ],
    )

    calldata = selector + encoded_args
    return to_hex(calldata)


def main():
    client = ENRGClient()

    print("=== Step 1: /health ===")
    print(client.health())

    print("\n=== Step 2: POST /oracle/attest (new format) ===")
    oracle_resp = client.oracle_attest_request(
        device_id="dev_demo_calldata",
        nonce="nonce_calldata_123",
        max_power_kw=3.3,
    )
    print(json.dumps(oracle_resp, indent=2))

    print("\n=== Step 3: Build full Attestation from oracle response ===")
    full_att = build_full_attestation_from_oracle_response(oracle_resp)
    print(json.dumps(full_att, indent=2))

    print("\n=== Step 4: Build on-chain params via build_attestation_params ===")
    params = build_attestation_params(full_att)
    print("On-chain parameters:")
    print(f"  attestationId (bytes32): 0x{params.attestation_id.hex()}")
    print(f"  deviceId      (bytes32): 0x{params.device_id.hex()}")
    print(f"  allowed       (bool)   : {params.allowed}")
    print(f"  maxPowerW     (uint64) : {params.max_power_w}")
    print(f"  issuedAt      (uint64) : {params.issued_at}")

    print("\n=== Step 5: Build calldata for submitAttestation(...) ===")
    calldata = build_submit_attestation_calldata(params)
    print(f"function selector: 0x{keccak(text='submitAttestation(bytes32,bytes32,bool,uint64,uint64)')[:4].hex()}")
    print(f"calldata: {calldata}")
    print("\nYou can use this calldata with eth_sendRawTransaction or cast send, e.g.:")
    print("  cast send <CONTRACT_ADDRESS> \"submitAttestation(bytes32,bytes32,bool,uint64,uint64)\" "
          "\"0x{att}\" \"0x{dev}\" {allowed} {max_power_w} {issued_at}".format(
              att=params.attestation_id.hex(),
              dev=params.device_id.hex(),
              allowed=str(params.allowed).lower(),
              max_power_w=params.max_power_w,
              issued_at=params.issued_at,
          ))


if __name__ == "__main__":
    main()
