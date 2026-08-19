# Axis Core — Documentation

This directory contains implementation-specific documentation for **Axis Core**, the
universal reference implementation of the Axis Protocol.

The normative protocol specification lives in the
[Axis-protocol](https://github.com/AntonGrid/Axis-protocol) repository. Documents
in this directory are **informative** for the protocol and describe the reference
implementation only.

---

## Directory Structure

```text
docs/
├── README.md                       # This file
├── Axis-Governance-and-ADR.md      # Governance and ADR/RFC process
├── Axis-One-Pager.md               # High-level overview
├── Axis-Terminology.md             # Terminology reference
├── merkle-proof-verification.md    # Merkle proof verification
├── implementation/
│   ├── api.md                      # HTTP API reference
│   ├── onchain-attestation.md      # Attestation → on-chain mapping
│   ├── architecture.md             # (legacy) ENRG product architecture notes
│   └── axis-architecture.md        # Axis protocol & domain integration overview
└── platform/
    ├── device-lifecycle.md         # Device lifecycle (implementation view)
    └── provisioning.md            # Provisioning service specification
```

---

## Entry Points

1. **API** — start with [`implementation/api.md`](./implementation/api.md) and the
   repository-level [`API.md`](../API.md) and [`openapi.yaml`](../openapi.yaml).
2. **JSON Schemas** — see [`SCHEMAS.md`](../SCHEMAS.md) and the `schemas/` directory.
3. **Platform** — device lifecycle and provisioning are described in
   `platform/` (implementation view; the normative documents live in Axis-protocol).
4. **On-chain integration** — `implementation/onchain-attestation.md` describes how
   an Attestation is mapped to on-chain parameters.

---

## Relationship to the Protocol

- **Axis Protocol** defines the normative trust model, wire format, validation rules,
  and lifecycles.
- **Axis Core** implements those rules and documents any deployment-specific choices
  here.

Conformance of this implementation with the Axis Protocol is verified by the
conformance tests in `tests/` (see the “Conformance” section of the README).
