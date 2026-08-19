# ENRG Demo & Integration Guide

This repository contains a minimal end-to-end demo for ENRG Attestations
and on-chain integration.

The main flow:

1. **Get an Attestation** from the ENRG Oracle.
2. **Validate** it against the Attestation schema (`schema_version: "1.0"`).
3. **Convert** it into on-chain parameters and calldata for
   `submitAttestation(...)`.
4. **Send** the calldata with your own transaction builder on the target chain
   (testnet or mainnet).

---

## 1. Backend: REST API & Schemas

For details on the HTTP API and payload formats, see:

- `API.md` — HTTP endpoints (including `/oracle/attest`).
- `SCHEMAS.md` — JSON schemas for:
  - `Attestation` (v1.0),
  - `OracleAttestRequest`.

The key object is the **Attestation** with:

- `schema_version: "1.0"`
- `attestation_id`
- `device_id`
- `decision.allowed` (bool)
- `decision.max_power_kw`
- `issued_at` (ISO 8601, UTC)
- `oracle_signature` (opaque field for off-chain verification)

---

## 2. Running the local demo

### 2.1. Start the backend

From the repo root:

```bash
uvicorn axis_core.main:app --reload --port 8000
Check that it is up:

bash
curl http://localhost:8000/health
2.2. Happy-path online demo
Runs the full chain:

/health → /oracle/attest (allowed = true) → build Attestation (v1.0) → build on-chain params → build calldata for submitAttestation(...)

bash
python scripts/full_oracle_onchain_calldata_demo.py \
  --device-id dev_demo_full_cycle \
  --max-power-kw 3.3
You will see:

human-readable parameters:

attestationId (bytes32)

deviceId (bytes32)

allowed (bool)

maxPowerW (uint64)

issuedAt (uint64)

ABI-encoded calldata for:

solidity
function submitAttestation(
  bytes32 attestationId,
  bytes32 deviceId,
  bool allowed,
  uint64 maxPowerW,
  uint64 issuedAt
);
2.3. Deny-case online demo
Same flow, but forces allowed = false to demonstrate the refusal case:

bash
python scripts/oracle_deny_onchain_calldata_demo.py \
  --device-id dev_demo_deny \
  --max-power-kw 10.0
Output is similar, but:

allowed is false;

calldata encodes allowed = false.

3. Offline demo: from JSON to calldata
If you already have an Attestation JSON (for example, produced by your system or stored off-chain), you can go straight from JSON to calldata.

3.1. Input
By default the script expects:

attestation-example.json in the repo root, matching attestation.schema.json with schema_version: "1.0".

3.2. Build calldata
bash
python scripts/send_attestation_onchain.py \
  --attestation-file attestation-example.json
The script will:

Load the Attestation JSON.

Normalize it for schema_version: "1.0" (if missing, it is added).

Call axis_core.onchain_bridge.build_attestation_params(...).

Print on-chain parameters and ABI-encoded calldata for submitAttestation(...).

The script does not send any transaction — it only prints data.

4. Mainnet integration in 3 steps
The demo scripts are chain-agnostic: they do not know about RPC URLs, chain IDs or contract addresses. To use them for mainnet integration:

Step 1 — Agree on the Attestation format (off-chain)
Use SCHEMAS.md and axis_core/schemas/attestation.schema.json as the source of truth.

Pin schema_version: "1.0" for the integration.

Decide:

how Attestations are stored (database, file, other system),

how you retrieve them (REST, message bus, etc.).

Step 2 — Produce or fetch an Attestation
Two options:

Online (through ENRG backend)

Call /oracle/attest as in scripts/full_oracle_onchain_calldata_demo.py.
Store the resulting Attestation JSON (or pass it directly to your pipeline).

Offline

Use an Attestation JSON file that already conforms to the schema.
Validate it locally if needed (e.g., with jsonschema).

Step 3 — Feed the Attestation into your on-chain sender
Pick one of the scripts as a reference implementation:

scripts/send_attestation_onchain.py

scripts/full_oracle_onchain_calldata_demo.py

scripts/oracle_deny_onchain_calldata_demo.py

Use them in one of two ways:

3.1. Direct use of the generated calldata
Run a script and copy the produced calldata.

Build and send the transaction on your side:

to = deployed ENRG contract address on mainnet,

data = the calldata string,

value = 0,

chainId, gas, fees = according to your mainnet setup.

3.2. Embed the bridge logic into your code
Reuse the Python function:

python
from axis_core.onchain_bridge import build_attestation_params
Or reimplement the same logic in your language of choice:

attestationId and deviceId are hashed to bytes32,

decision.allowed becomes bool allowed,

decision.max_power_kw is converted to uint64 maxPowerW,

issued_at (ISO string) is converted to uint64 Unix timestamp.

Then call your contract binding, for example (pseudo-code):

solidity
await contract.submitAttestation(
  attestationId,   // bytes32
  deviceId,        // bytes32
  allowed,         // bool
  maxPowerW,       // uint64
  issuedAt         // uint64
);
5. What remains on the integrator side
The ENRG demo covers:

Attestation format and validation;

conversion to on-chain parameters;

building ABI-encoded calldata.

The integrator is responsible for:

deploying or referencing the on-chain contract with submitAttestation(...);

choosing network, RPC, and chain ID;

configuring gas, fees, nonces and retries;

key management and transaction signing;

monitoring on-chain results and events.

For more details on the on-chain side, see:

onchain/README.md — contract function, calldata examples, mainnet checklist.

6. Integrator checklist
Use this checklist as a minimal guide to integrate ENRG Attestations with your on-chain flow.

Agree on the Attestation format
Confirm that you use schema_version: "1.0".

Align on the fields: attestation_id, device_id, decision.allowed, decision.max_power_kw, issued_at, oracle_signature.

Decide how you get Attestations:

Online: via ENRG /oracle/attest endpoint.

Offline: from your own storage / another system, already matching the schema.

Validate Attestations (optional but recommended)
Use SCHEMAS.md and axis_core/schemas/attestation.schema.json.

Optionally validate locally using jsonschema.

Run the local demo once
Start the backend:

bash
uvicorn axis_core.main:app --reload --port 8000
Run the happy-path demo:

bash
python scripts/full_oracle_onchain_calldata_demo.py \
  --device-id dev_demo_full_cycle \
  --max-power-kw 3.3
Make sure you see both parameters and calldata for submitAttestation(...).

Test the deny case
Run:

bash
python scripts/oracle_deny_onchain_calldata_demo.py \
  --device-id dev_demo_deny \
  --max-power-kw 10.0
Confirm that allowed is false and calldata encodes allowed = false.

Choose integration mode
Mode A — JSON → ENRG script → calldata → your sender

Use scripts/send_attestation_onchain.py or scripts/full_oracle_onchain_calldata_demo.py.

Take the printed calldata and plug it into your transaction builder.

Mode B — JSON → ENRG bridge logic → your contract binding

Reuse axis_core.onchain_bridge.build_attestation_params(...) in your backend or reimplement its logic in your language.

Call your contract binding's submitAttestation(...) with the derived parameters.

Prepare mainnet configuration
RPC URL and chainId of the target network.

Deployed ENRG contract address with submitAttestation(...).

Operator key / signer for sending transactions.

Gas and fee policy (gas limits, max fee, retries).

Wire into your production pipeline
Insert the "Attestation → params → calldata/contract call" step into your existing flow (e.g. before enabling power, minting, or updating device state).

Log:

source Attestation JSON,

derived parameters,

transaction hash and status.

Monitor and operate
Subscribe to contract events and/or transaction receipts.

Build basic alerts for failed transactions or unexpected allowed = false.

Periodically re-run the demo scripts after upgrades to ensure compatibility.

Plan for schema upgrades
If you move away from schema_version: "1.0", make a migration plan:

update JSON schema,

update bridge logic,

re-run tests and demos,

update docs (API.md, SCHEMAS.md, onchain/README.md, README_demo.md).
