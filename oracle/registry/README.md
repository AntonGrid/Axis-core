# Axis Manifest Registry

The Manifest Registry is a reference service of **Axis Core**. It publishes signed device manifests and produces Merkle snapshots for downstream oracles, verifiers, and digital systems.

> This is a **platform-agnostic** reference implementation. The registry does not depend on any specific blockchain or domain.

## Features

- Publish signed manifests via `POST /api/v1/manifests`
- Retrieve a manifest by id via `GET /api/v1/manifests/:id`
- Create a Merkle snapshot via `POST /api/v1/merkle/snapshot`
- Read the latest Merkle root via `GET /api/v1/merkle/current`
- Health check at `GET /health`

## Local run

### With Node.js

```bash
cd oracle/registry
npm install
REGISTRY_ADMIN_KEY=secure-key node server.js
```

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

Create a Merkle snapshot:

```bash
curl -X POST http://localhost:4000/api/v1/merkle/snapshot \
  -H 'x-api-key: secure-key'
```

A ready-to-use publisher utility lives in `tools/publisher.js`.

