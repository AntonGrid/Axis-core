# Axis Manifest Registry

The Manifest Registry is a reference service of **Axis Core**. It publishes signed device manifests and produces Merkle snapshots for downstream oracles, verifiers, and digital systems.

> This is a **platform-agnostic** reference implementation. The registry does not depend on any specific blockchain or domain.

## Features

- Publish signed manifests via `POST /api/v1/manifests`
- Retrieve a manifest by id via `GET /api/v1/manifests/:id`
- Create a Merkle snapshot via `POST /api/v1/merkle/snapshot`
- Read the latest Merkle root via `GET /api/v1/merkle/current`
- Get a per-leaf Merkle membership proof via `GET /api/v1/merkle/proof/:manifestId`
- Health check at `GET /health`

## Local run

### With Node.js

```bash
cd oracle/registry
npm install
REGISTRY_ADMIN_KEY=your-admin-key node server.js
```

> `REGISTRY_ADMIN_KEY` is **required** — the registry exits with an error if it
> is not set. It guards `POST /api/v1/merkle/snapshot`; choose a strong, random
> value and do not commit it.

### Run tests

```bash
cd oracle/registry
npm install
npm test
```

The registry will be available at http://localhost:4000.

> To run the full stack (Axis Core API + Manifest Registry) with Docker Compose,
> use the `docker-compose.yml` at the repository root:
> `docker compose up --build`.
> To containerize the registry alone, build the included `Dockerfile`:
> `docker build -t axis-manifest-registry ./oracle/registry`.

## Example requests

Publish a manifest:

```bash
curl -X POST http://localhost:4000/api/v1/manifests \
  -H 'Content-Type: application/json' \
  -d '{"manifest_id":"demo-1","payload":{"manifest_version":"1.0","device_type":"sensor"},"signature":"dGVzdC1zaWduYXR1cmU=","public_key":"dGVzdC1wdWJsaWMta2V5"}'
```

Create a Merkle snapshot (use the same `REGISTRY_ADMIN_KEY` the registry was
started with):

```bash
curl -X POST http://localhost:4000/api/v1/merkle/snapshot \
  -H 'x-api-key: your-admin-key'
```

## Known limitations

- **In-memory storage.** Published manifests and snapshots are kept in memory
  and are lost on restart. Persistence is a separate milestone.
- **16-byte `manifest_id`.** For on-chain compatibility (`verify_merkle_proof`
  expects `manifest_id: [u8; 16]`), the registry rejects ids that are not
  exactly 16 bytes (UTF-8).

## Merkle format (on-chain compatible)

Snapshots use a SHA-256 Merkle tree that is bit-compatible with the ENRG
on-chain verifier (`merkle_proof_verification.rs`) and the reference client
helpers (`ENRG/tests/helpers/merkle.ts`):

```text
leaf = SHA-256(manifest_id(16) || content_hash(32))
node = SHA-256(left(32) || right(32))        // single hash
```

- `content_hash = SHA-256(canonical JSON payload)` (canonical = sorted keys,
  no whitespace — see `app.js` `canonicalize`).
- Odd levels duplicate the last node.
- A leaf's `position` is its index in the snapshot; proof siblings alternate
  left/right based on the position bits (exactly as the on-chain
  `compute_merkle_root` expects).

The publisher that registers a manifest on-chain MUST use the same
`content_hash` so the leaf matches `ManifestVerification.content_hash`.

A ready-to-use publisher utility lives in `tools/publisher.js`.

