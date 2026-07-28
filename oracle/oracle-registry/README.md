# Axis Core — Oracle Registry

This service manages the registry of trusted oracles for the Axis Protocol.

## Endpoints

- `POST /register` — register a new oracle
- `GET /list` — list all registered oracles
- `POST /verify` — verify an oracle's signature

## Configuration

- `REGISTRY_DB` — path to the SQLite database
- `TRUSTED_KEYS` — list of trusted public keys
