# Axis Core

**Axis Core** is the **universal reference implementation** of the [Axis Protocol](https://github.com/AntonGrid/Axis-protocol) — an open, implementation-independent standard for establishing cryptographically verifiable trust between physical devices and digital systems.

This repository contains the **platform-agnostic** executable parts of the Axis stack:

- **Core services** — Provisioning, Device Registry, Oracle (attestation decision) logic
- **Manifest Registry** — a reference service for signed device manifests and Merkle snapshots
- **Schemas & validation** — canonical JSON Schemas and runtime validation
- **Developer tooling** — demo scripts, tests, and examples

> **Note:** This is the **universal** implementation. Blockchain-specific bindings (e.g., Solana, EVM) and domain-specific applications (e.g., energy tokenization) live in separate repositories and profiles — see [ENRG](https://github.com/AntonGrid/ENRG) as one example of a domain profile.

---

## Repository Structure

```text
Axis-core/
├── axis_core/              # Python package (FastAPI backend)
│   ├── api/                # REST API endpoints (provisioning, registry, oracle)
│   ├── services/           # Business logic (Provisioning, Registry)
│   ├── schemas/            # Runtime JSON Schemas (validated with jsonschema)
│   ├── main.py             # FastAPI application entry point
│   ├── onchain_bridge.py   # Attestation → on-chain parameter mapping (chain-agnostic)
│   ├── oracle_storage.py   # In-memory oracle storage
│   ├── schema_utils.py     # JSON Schema loading / validation helpers
│   └── schemas_loader.py   # Attestation schema loader
├── schemas/                # Canonical JSON Schemas (reference copies)
├── oracle/
│   └── registry/           # Manifest Registry (Node.js / Express)
├── scripts/                # Demo and utility scripts
├── tests/                  # pytest test suite
├── docs/                   # Implementation-specific documentation
├── adr/                    # Implementation-level ADRs
├── openapi.yaml            # OpenAPI description of the public API
├── API.md                  # API overview
├── SCHEMAS.md              # JSON Schema reference
├── ROADMAP.md              # Roadmap
├── LICENSE                 # Apache 2.0
└── requirements.txt        # Python dependencies
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the Manifest Registry)

### Install

```bash
git clone https://github.com/AntonGrid/Axis-core.git
cd Axis-core

# Python (create and use a virtual environment)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (Optional) Manifest Registry
cd oracle/registry && npm install && cd ../..
```

### Run the backend

```bash
uvicorn axis_core.main:app --reload --port 8000
```

### Run the Manifest Registry (optional)

```bash
cd oracle/registry
REGISTRY_ADMIN_KEY=secure-key node server.js
```

### Run with Docker Compose (optional)

The repository ships a `docker-compose.yml` that brings up both services:

```bash
docker compose up --build
```

> **Requires Docker Compose v2** (`docker compose`). Verify with
> `docker compose version` before running. The legacy `docker-compose` (v1)
> binary is not supported.

- Axis Core API → http://localhost:8000
- Manifest Registry → http://localhost:4000

Set `AXIS_ALLOW_MOCK=1` to enable the dev-only mock signature mode.

---

## Tests

```bash
# Python tests
pytest -q

# Manifest Registry tests
cd oracle/registry && npm test

# Or run everything from the repo root
./run-tests.sh
```

---

## Quick Start

1. Start the backend (see above) and check health:

   ```bash
   curl http://localhost:8000/health
   # => {"status": "ok"}
   ```

2. Register a device:

   ```bash
   curl -X POST http://localhost:8000/provisioning/register \
     -H 'Content-Type: application/json' \
     -d '{"public_key": "test-public-key-1"}'
   ```

3. Submit a signed device proof to the oracle (real Ed25519 flow via the demo script —
   it generates a key, registers the device, and signs the proof):

   ```bash
   python scripts/full_oracle_onchain_demo.py
   ```

   > **Note:** the oracle now verifies Ed25519 signatures. A device must be
   > registered first, and `proof.signature` must be valid over the canonical
   > message (see [docs/conformance.md](./docs/conformance.md)). The legacy
   > `mock` algorithm is a dev-only mode enabled with `AXIS_ALLOW_MOCK=1`.

4. Explore the full attestation → on-chain mapping demos:

   ```bash
   python scripts/demo_onchain_bridge.py            # from attestation-example.json
   python scripts/send_attestation_onchain.py        # JSON → calldata
   python scripts/full_oracle_onchain_calldata_demo.py   # live /oracle/attest → calldata
   ```

See [README_demo.md](./README_demo.md), [API.md](./API.md), and [SCHEMAS.md](./SCHEMAS.md) for details.

---

## Relationship with Other Repositories

- **Axis-protocol** — canonical protocol specification (trust model, wire format, validation, lifecycle). This is the *source of truth* for the protocol.
- **Axis-core** (this repository) — universal reference implementation of the protocol.
- **ENRG** — a domain-specific application (energy) with a blockchain binding; an example of how Axis Core can be extended for a specific domain.

---

## Architecture

Axis Core follows the same architectural principles as the Axis Protocol:

- **Open Standard** — anyone can implement, modify, and extend.
- **Domain-Agnostic** — no assumptions about energy, supply chain, finance, etc.
- **Infrastructure-Agnostic** — no dependency on a specific blockchain or runtime.
- **Trust Minimization** — cryptographic verification replaces blind trust.
- **Separation of Concerns** — each component has a single, well-defined responsibility.
- **Key Never Leaves the Device** — the core only verifies proofs; it never holds private keys.

For a deeper dive, read the [Architecture Decision Records](https://github.com/AntonGrid/Axis-protocol/tree/main/adr) and the [Axis Protocol Specification](https://github.com/AntonGrid/Axis-protocol).

---

## Conformance

Axis Core aims to be a faithful reference implementation of the [Axis Protocol](https://github.com/AntonGrid/Axis-protocol).

The conformance tests in `tests/test_conformance.py` verify:

- the committed [`openapi.yaml`](./openapi.yaml) matches the actual FastAPI routes;
- the canonical schemas in `schemas/` stay in sync with the runtime schemas in `axis_core/schemas/`;
- schema field names follow the protocol glossary;
- the attestation examples (`attestation-example.json`, `attestation-example-deny.json`)
  are schema-valid and round-trip through the oracle API (allowed and denied scenarios);
- the oracle verifies real Ed25519 device signatures (registered device, canonical
  signed message) and rejects unregistered devices and invalid signatures.

Known deviations and gaps (manifest vs ADR-0004, lifecycle states, wire format,
mock policy engine) are **documented, not silently changed** — see
[docs/conformance.md](./docs/conformance.md).

---

## Contributing

We welcome contributions! Please read:

- [CONTRIBUTING.md](./CONTRIBUTING.md) — guidelines for PRs and coding standards
- [SECURITY.md](./SECURITY.md) — for reporting security issues
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) — community standards

---

## License

Apache 2.0 © 2026 Anton Gulda

