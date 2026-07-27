
# Axis Protocol

Axis Protocol is a domain-agnostic trust and attestation framework that connects physical devices and digital systems.

This repository contains the **Axis Core** specification and reference implementation.  
Domain-specific modules (for example, the ENRG Energy domain) are built **on top of Axis Core** in separate repositories.

## High-level goals

- Provide a standardized way to:
  - identify devices and actors
  - issue, verify, and revoke on-chain attestations
  - manage registries (manifests, capabilities, events, errors)
  - define and enforce policies and governance
- Stay domain-agnostic, so different verticals (energy, mobility, IoT, etc.) can implement their own domain modules.

## Repository structure (draft)

> This structure is in progress and will be refined.

- `docs/` – Axis Protocol specifications (terminology, architecture, conformance, ADR/RFC, governance).
- `schemas/` – core JSON schemas for manifests, capabilities, events, errors.
- `programs/` / `onchain/` – on-chain reference implementation for core attestation and registries.
- `sdk/` – client libraries and tools to interact with Axis Core.
- `examples/` – example flows and integration patterns.

## Status

Axis Core is being refactored from an energy-specific prototype (ENRG) into a domain-agnostic protocol.  
Expect breaking changes and frequent updates while this cleanup is in progress.
