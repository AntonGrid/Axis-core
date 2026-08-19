# ADR-0006: Core Protocol vs Domain Profile

**Status:** Proposed  
**Date:** 2026-07-16  
**Authors:** Axis Core Team  

> **Note.** This is the implementation-level ADR that originated the split between
> the core protocol and domain profiles. The canonical, protocol-level decision is
> recorded as ADR-0006 in the Axis-protocol repository.

## 1. Context

Two different layers are often mixed up in internal discussions and external
communication:

1. **The protocol itself**  
   — an abstract, decentralized infrastructure layer for:
   - cryptographic identification of real devices and processes;
   - generation and verification of proofs of real-world events (Proofs);
   - running economic mechanisms (emission, rewards, DAO) on top of those proofs.

2. **A concrete domain scenario (Energy Profile v1)**  
   — the first instantiation of the protocol in the energy domain:
   - devices: inverters, meters, ESP32 gateways, etc.;
   - measured quantity: Wh/kWh/MWh;
   - event type: energy production/consumption/balancing.

Historically, the protocol was often described as an “energy protocol” or a
“renewable energy protocol”. This is convenient for explanations, but:

- it creates the false impression that the protocol is **tightly coupled to energy**;
- it limits thinking when designing other domains (IoT, industrial sensors,
  climate metrics, etc.);
- it prevents separating the **protocol core** from concrete usage profiles.

The architecture must formally capture:  
**what exactly is the Core**, what a **Domain Profile** is, and how we talk about
both in all documents.

---

## 2. Problem

Without this separation, systemic problems arise:

1. **Semantic confusion**
   - Phrases like “the protocol pays for energy” or “1 MWh = 1 token” imply that:
     - the token is a commodity,
     - the protocol is an electricity market.
   - In reality:
     - the protocol does not “know” about energy as a commodity at all,
     - it operates on *events and proofs*.

2. **Architectural constraints**
   - Developers and partners start to believe that:
     - the protocol cannot be applied to IoT outside energy,
     - all on-chain models are permanently hard-wired to kWh/MWh.
   - This complicates scaling to other real-world domains.

3. **Regulatory and legal risks**
   - Wording about “payment for electricity” or the “price of MWh”:
     - may lead to the token being treated as a direct surrogate of a commodity
       or a means of payment,
     - although in fact the token is a **native protocol incentive token**, not a
       cash equivalent of electricity.

4. **Documentation inconsistency**
   - Different documents describe the protocol differently:
     - sometimes as an energy protocol,
     - sometimes as a general “proof + reward layer”.
   - New team members, auditors, and partners get a contradictory picture.

An explicit and stable architectural agreement is required.

---

## 3. Decision

We separate the notions of the **Core Protocol** and **Deployment Profiles**, and
formalize the **Energy Profile v1** as the first deployment profile.

### 3.1. Definition: Core Protocol

> **The Core is an open, decentralized infrastructure protocol for the
> cryptographic capture and economic reward of trustworthy real-world events.**

The Core defines:

1. **Device / actor identity**
   - A device identity model (keys, binding to owner/operator).
   - Device registries (on-chain / off-chain with on-chain anchors).

2. **Message and proof model**
   - Device message format (for example, `{device_id, timestamp, value, nonce, signature}`).
   - Cryptographically required fields for validation (nonce, ranges, monotonicity, etc.).

3. **Role and interfaces of oracles**
   - As off-chain orchestrators that:
     - collect and verify the raw data stream,
     - form aggregated **Oracle Reports**,
     - sign them and submit them on-chain.

4. **On-chain validation of reports**
   - Verification of the report signature and structure.
   - Verification of device identity, nonce, time, limits, and policies.
   - Acceptance or rejection of the report as a network event.

5. **Economic primitives**
   - The emission function: `reward = f(event, total_supply)`  
     (in the current implementation — an asymptotic model with increasing difficulty).
   - A native token minting mechanism.
   - Reward distribution (producer vs protocol funds).
   - A basic staking / treasury / DAO model.

6. **Guarantees and invariants**
   - A fixed `MAX_SUPPLY`.
   - Emission is tied only to verified events.
   - Explicit separation of:
     - the **physical domain** (what exactly is measured),
     - the **protocol domain** (which events and proofs are considered valid).

Important: **the Core has no “energy” as a hard-coded entity**.  
It only deals with abstract:

- devices,
- measurements,
- proofs,
- events,
- economic reactions to them.

### 3.2. Definition: Deployment Profile

> **A Deployment Profile is a concrete instantiation of the Core in a given
> real-world domain.**

The profile defines:

- what exactly is considered an **event**;
- which **device types and measurements** are supported;
- which **additional validation rules** apply (domain business logic);
- how all of this maps to the Core model (which fields appear in Proofs, what the
  boundaries are, what the units of measurement are, etc.).

Profiles can include:

- Energy v1 (energy),
- IoT v1 (general sensors),
- Climate v1 (climate data), etc.

### 3.3. Definition: Energy Profile v1

> **Energy v1 is the first deployment profile in which the objects of events are
> energy events (production/consumption/balancing of energy).**

In Energy v1:

- **Event**:  
  “Device X, owned by participant Y, recorded at time T a change in the energy meter
  reading of ΔWh, confirmed by the device signature and verified by the oracle.”
- **Devices**:  
  inverters, meters, ESP32 gateways, and similar devices capable of:
  - stably measuring energy,
  - signing data with their own key.
- **Measured quantity**:  
  energy in Wh/kWh/MWh (choosing units is part of the profile, not the core).
- **Profile-specific checks**:
  - monotonicity of readings,
  - allowed bounds for power and total generation,
  - compliance with geography / grid parameters (if required).

Key point:  
**this is only a specific “skin” on the Core**, not a protocol entity.

### 3.4. The native token in the context of Core and Profiles

> **The native token is the Core's incentive token, issued for confirmed
> real-world events.**

- In Energy v1 an event is an energy event.
- In another profile (for example, IoT) an event may be different (sensor
  traffic, industrial telemetry, etc.).
- At the Core level:
  - the token **is not “payment for kilowatt-hours”**,
  - the token **does not fix a “price per MWh”**,
  - the token **is tied to validated events**, not to a commodity.

The default wording:

- “The token is an economic mechanism of the protocol that serves the trust layer,
  not the goal of the protocol by itself.”

---

## 4. Consequences

### 4.1. What changes in documentation

1. **In all key documents** (whitepaper, README, economics ADRs, presentations):
   - introduce an explicit separation of:
     - the Core,
     - the Energy v1 (and subsequent profiles).
   - Phrases such as:
     - “the protocol pays for electricity”,
     - “1 MWh = 1 token”  
     are **prohibited** or marked as historical/legacy.

2. **New sections / edits**:
   - `docs/core/what-is-core.md` — a basic domain-neutral description.
   - `docs/profiles/energy-v1.md` — the specifics of the energy profile.
   - Economics ADRs (emission, funds, staking) describe:
     - the general model (at the Core level),
     - the concrete energy binding — only within the relevant profile.

### 4.2. What changes in communication

- Externally:
  - “The protocol is a trust and incentive layer for real-world events; our first
    profile is energy.”
- Internally:
  - any architectural discussion starts by clarifying:
    - are we talking about the **Core**,
    - or about a specific **Profile (Energy / IoT / …)**?

### 4.3. Pros

- Clear separation of responsibilities:
  - the Core is responsible for cryptography, validation, and economics;
  - profiles are responsible for domain specifics.
- Easy scaling to other domains without breaking the core.
- Reduced regulatory/legal risks:
  - the token is not positioned as “direct payment for energy”.
- Better readability for audits:
  - the auditor sees that the protocol is a general layer and energy is a
    concrete application.

### 4.4. Cons / risks

- Required work:
  - go through all existing documents and remove “energy-centric” language where
    the Core is meant;
  - introduce discipline in using terms in communication and code.
- Possible transitional wording:
  - for a while, old materials will contradict the new structure until updated.

---

## 5. Alternatives Considered

1. **Keep everything as is (protocol = energy protocol)**  
   Rejected because it:
   - limits scalability,
   - creates unnecessary regulatory risks,
   - prevents a clear separation of layers.

2. **Fork the branding (a separate name for Core, a separate one for Energy)**  
   Rejected for now because:
   - it complicates the brand and communication,
   - Core and Energy remain in one project; separation in documentation is enough.

---

## 6. Implementation Notes

- This ADR must be:
  - placed in `adr/`,
  - linked from the README and the architecture overview.
- The following ADRs (economics, proof model, Ed25519/oracle model):
  - must explicitly state whether they refer to:
    - the Core,
    - a specific deployment profile (and which one).
