# Axis Core — Oracle Server

This server receives signed proofs from IoT devices, verifies Ed25519 signatures, accumulates data, and automatically calls the on-chain program when the threshold is reached.

## Quick Start
1. Install dependencies: `npm install`
2. Place your founder keypair at `~/founder-keypair.json` (64-byte array)
3. Register device public keys in `devices.json` (base64-encoded Ed25519 public key)
4. Start the server: `node server.js`

## API
- `POST /api/v1/proof/submit` — submit a signed proof
- Body: `{ device_id, timestamp, energyWh, nonce, signature }`

## Configuration
- `THRESHOLD` — units to accumulate before minting (default: 1,000,000)
- `PROGRAM_ID` — deployed program address
- `MINT_ADDRESS` — token mint (if applicable)
