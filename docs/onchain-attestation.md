ENRG On-chain Attestation Mapping
=================================

Off-chain Attestation (JSON)
----------------------------

Пример (attestation-example.json):

{ 
  "attestation_id": "att_1a2b3c4d5e6f7890",
  "device_id": "dev_9e9c644e1580a83b",
  "proof": { "...": "..." },
  "decision": {
    "allowed": true,
    "reason": "mock-allowed",
    "max_power_kw": 2.5
  },
  "oracle_id": "oracle_main_1",
  "issued_at": "2026-07-25T19:05:00Z",
  "oracle_signature": "cafebabecafe..."
}

On-chain контракт
-----------------

Сигнатура функции в контракте EnrgOracleAttestation:

function submitAttestation(
    bytes32 deviceId,
    bool allowed,
    int96 maxPowerKw,
    uint64 issuedAt,
    bytes32 proofHash
) external;

Маппинг полей
-------------

deviceId (bytes32)  = keccak256(bytes(att.device_id))
allowed (bool)      = att.decision.allowed
maxPowerKw (int96)  = int96(att.decision.max_power_kw * 1e6)
                     пример: 2.5 → 2_500_000
issuedAt (uint64)   = Unix timestamp из att.issued_at
proofHash (bytes32) = keccak256(bytes(serialize(att)))
                     (либо keccak256(bytes(serialize(att.proof))), если хотим отделить слои)

Итого: богатый off-chain JSON → компактный набор чисел/хэшей on-chain.
