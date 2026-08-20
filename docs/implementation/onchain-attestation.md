# On-chain Attestation Bridge

## 1. Off-chain Attestation format (JSON)

Example (`attestation-example.json`):

```json
{
  "attestation_id": "att_1a2b3c4d5e6f7890",
  "device_id": "dev_9e9c644e1580a83b",
  "proof": {
    "device_id": "dev_9e9c644e1580a83b",
    "nonce": "abc12345xyz",
    "timestamp": "2026-07-25T19:00:00Z",
    "algo": "mock",
    "payload": { "max_power_kw": 2.5 },
    "signature": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
  },
  "decision": {
    "allowed": true,
    "reason": "mock-allowed",
    "max_power_kw": 2.5
  },
  "oracle_id": "oracle_main_1",
  "issued_at": "2026-07-25T19:05:00Z",
  "oracle_signature": "cafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebabe"
}
```

## 2. On-chain structure (reference contract)

The reference on-chain interface receives the core attestation fields:

```solidity
struct AttestationCore {
    bytes32 attestationId;
    bytes32 deviceId;
    bool allowed;
    uint64 maxPowerW;
    address oracle;
    uint64 issuedAt; // unix timestamp
}

function submitAttestation(
    bytes32 attestationId,
    bytes32 deviceId,
    bool allowed,
    uint64 maxPowerW,
    uint64 issuedAt
) external;
```

`msg.sender` is the trusted oracle (checked against the contract's trusted-oracle
set). The attestation is stored in a public mapping, e.g.
`mapping(bytes32 => AttestationCore) public attestations`.

## 3. Mapping off-chain → on-chain

Path: `JSON → axis_core.adapters.evm.build_attestation_params(...) → parameters for submitAttestation`.

| Attestation field | On-chain parameter | Conversion |
| :--- | :--- | :--- |
| `attestation_id` (string) | `attestationId` (bytes32) | `attestationId = keccak(text=attestation["attestation_id"])` |
| `device_id` (string) | `deviceId` (bytes32) | `deviceId = keccak(text=attestation["device_id"])` |
| `decision.allowed` (bool) | `allowed` (bool) | direct |
| `decision.max_power_kw` (float, kW) | `maxPowerW` (uint64, W) | `maxPowerW = int(decision["max_power_kw"] * 1000)` |
| `issued_at` (ISO 8601, with "Z") | `issuedAt` (uint64, unix timestamp) | parse ISO 8601 (UTC) → unix timestamp |

## 4. Example parameters (from demo_onchain_bridge.py)

Command:

```bash
python scripts/demo_onchain_bridge.py
```

Example output:

```text
=== On-chain parameters for submitAttestation ===
attestationId (bytes32): 0x16c9c0ac191d642d6effa42f8d2a44612c003d2848ba10cf7b9df23206b236ea
deviceId      (bytes32): 0x54562bb25b54e0e36d75c1f38fef431a05f3de67bc51103fc1266257da876e63
allowed       (bool)   : True
maxPowerW     (uint64) : 2500
issuedAt      (uint64) : 1785006300
```

These values map directly to the contract call:

```solidity
submitAttestation(
    0x16c9c0ac191d642d6effa42f8d2a44612c003d2848ba10cf7b9df23206b236ea,
    0x54562bb25b54e0e36d75c1f38fef431a05f3de67bc51103fc1266257da876e63,
    true,
    2500,
    1785006300
);
```

`msg.sender` must be a trusted oracle, added via the contract's oracle management
function (e.g. `setTrustedOracle(address oracle, bool trusted)`).

## 5. Related documents

- `axis_core/adapters/evm.py` — bridge implementation.
- `scripts/demo_onchain_bridge.py`, `scripts/demo_onchain_bridge_deny.py` — demos.
- `scripts/full_oracle_onchain_calldata_demo.py` — live `/oracle/attest` → calldata flow.
- `SCHEMAS.md` — attestation schema reference.
