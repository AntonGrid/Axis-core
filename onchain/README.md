# ENRG On-chain Bridge & Demos

This directory contains documentation and helper scripts for bridging
ENRG Attestations into on-chain calls.

The core goal is to take a JSON Attestation (aligned with `schema_version: "1.0"`)
and turn it into parameters and calldata for the Solidity function:

```solidity
submitAttestation(
  bytes32 attestationId,
  bytes32 deviceId,
  bool allowed,
  uint64 maxPowerW,
  uint64 issuedAt
)
The heavy lifting (hashing, encoding) is done by:

app.onchain_bridge.build_attestation_params(attestation: dict)
1. Scripts overview
There are two main kinds of scripts:

Offline — start from a JSON file in the repo.
Online — call the ENRG backend (/oracle/attest) and then build an Attestation.
1.1 Offline scripts
a) scripts/demo_onchain_bridge.py

Input: attestation-example.json
Output: on-chain parameters.
Usage:

python scripts/demo_onchain_bridge.py
b) scripts/send_attestation_onchain.py

Input: Attestation JSON file (default: attestation-example.json).
Output: on-chain parameters + ABI-encoded calldata.
Usage:

python scripts/send_attestation_onchain.py \
  --attestation-file attestation-example.json
1.2 Online scripts (backend must be running)
Start the backend first:

uvicorn app.main:app --reload --port 8000
a) Happy-path: scripts/full_oracle_onchain_calldata_demo.py

Flow:

GET /health
POST /oracle/attest (new format, allowed = true)
Build full Attestation (schema_version: "1.0")
Build on-chain params via build_attestation_params
Build calldata for submitAttestation(...)
Example run:

python scripts/full_oracle_onchain_calldata_demo.py \
  --device-id dev_demo_full_cycle \
  --max-power-kw 3.3
Example on-chain output:

On-chain parameters for submitAttestation:
  attestationId (bytes32): 0xcb083111ab83d966a4ad56a49e42de588d0b8e1838934c23527a5414c283af27
  deviceId      (bytes32): 0xf04e15f5b2a378dfad0144b46fb0b0165f5fd73d2441156c09f14cc85a470f2f
  allowed       (bool)   : True
  maxPowerW     (uint64) : 3300
  issuedAt      (uint64) : 1785130443
Example calldata:

0x44b67025cb083111ab83d966a4ad56a49e42de588d0b8e1838934c23527a5414c283af27f04e15f5b2a378dfad0144b46fb0b0165f5fd73d2441156c09f14cc85a470f2f00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000ce4000000000000000000000000000000000000000000000000000000006a66edcb
This is a fully formed submitAttestation(...) calldata for the allow case.

b) Deny-case: scripts/oracle_deny_onchain_calldata_demo.py

Flow:

GET /health
POST /oracle/attest with parameters that trigger a deny (allowed = false)
Build full Attestation (schema_version: "1.0") from the oracle response
Ensure decision.allowed = false with a clear reason
Build on-chain params via build_attestation_params
Build calldata for submitAttestation(...) with allowed = false
Example run:

python scripts/oracle_deny_onchain_calldata_demo.py \
  --device-id dev_demo_deny \
  --max-power-kw 10.0
Example on-chain output:

On-chain parameters for submitAttestation (deny-case):
  attestationId (bytes32): 0x9d9a6305891382bea7ab6a1b881d7662383e3f8c5351dbfd37306a53b3da0e2c
  deviceId      (bytes32): 0xe46a234dd19c8e5491fc90dcf08df0e0557dc8974d01b7ce7e4ddfc68532da5d
  allowed       (bool)   : False
  maxPowerW     (uint64) : 10000
  issuedAt      (uint64) : 1785130731
Example calldata:

0x44b670259d9a6305891382bea7ab6a1b881d7662383e3f8c5351dbfd37306a53b3da0e2ce46a234dd19c8e5491fc90dcf08df0e0557dc8974d01b7ce7e4ddfc68532da5d00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002710000000000000000000000000000000000000000000000000000000006a66eeeb
This is a fully formed submitAttestation(...) calldata for the deny case.

The scripts do not send transactions — they only print arguments and calldata. You can feed this calldata into your own transaction builder / EOF tooling.

