# Provisioning Service Specification

**Status:** Draft v0.1

## Introduction

The Provisioning Service is responsible for device registration, identification,
and initial configuration within the Axis Protocol ecosystem. It serves as the
entry point for all new devices entering the trust pipeline.

---

## Device Registration Process

### Step 1: Key Generation

The device generates a cryptographic key pair on first boot:
- **Private Key** — remains on the device (never leaves it).
- **Public Key** — sent to the Provisioning Service for registration.

### Step 2: Registration Request

The device sends a request to the Provisioning Service containing:
- `device_id` — unique identifier (generated on the device).
- `public_key` — public key (Base64-encoded).
- `signature` — request signature (to prove key ownership).
- `device_type` — device type (Basic, Verified, Industrial).
- `firmware_version` — current firmware version.

### Step 3: Verification

The Provisioning Service verifies:
- Request signature.
- Uniqueness of `device_id`.
- No duplicate public keys exist.

### Step 4: Claim Code Generation

After successful verification, the server generates a **one-time Claim Code**
(8 characters, for example, `A7F4-K92Q`).

### Step 5: Response to Device

The device receives:
- `claim_code` — for user display.
- `status` — `registered`.
- `oracle_endpoint` — endpoint for sending Proofs.

### Step 6: Owner Linking (Claim)

The user enters the Claim Code in a Client Application. The device is then linked
to the Owner and transitions to the `CLAIMED` state.

---

## API Endpoints

### POST /identity/register

Register a new device.

**Request:**

```json
{
  "device_id": "esp32-001",
  "public_key": "pXZTI7zgANLzstGbXkX2hDxUtVBrT71Cb1ByGlCkcbw=",
  "signature": "...",
  "device_type": "Basic",
  "firmware_version": "1.0.0"
}
```

**Response:**

```json
{
  "claim_code": "A7F4-K92Q",
  "status": "registered",
  "oracle_endpoint": "https://oracle.axisprotocol.io"
}
```

### POST /identity/claim

Link a device to an owner using the Claim Code.

**Request:**

```json
{
  "claim_code": "A7F4-K92Q",
  "owner": "0x1234..."
}
```

**Response:**

```json
{
  "status": "claimed",
  "device_id": "esp32-001"
}
```

### GET /identity/status

Check device status.

**Response:**

```json
{
  "device_id": "esp32-001",
  "state": "ACTIVE",
  "owner": "0x1234...",
  "last_heartbeat": "2026-07-27T12:00:00Z"
}
```

> **Implementation note:** the current Axis Core reference implementation exposes
> provisioning through `/provisioning/register` and `/provisioning/attest`
> (see `API.md`). The `/identity/*` endpoints above describe the protocol-level
> API (see Axis-protocol `docs/platform/provisioning.md`).

---

## Normative Requirements

- **Key Security:** Private keys MUST never leave the device (see ADR-0001).
- **Signature Verification:** All requests MUST be signed and verified.
- **Claim Codes:** One-time use only; expire after a configurable period.
- **State Management:** Device state MUST be stored in the Device Registry (see ADR-0002).
- **Trust Preservation:** Registration MUST preserve the chain of trust.

---

## Related Documents

- ADR-0001: Private Key Never Leaves the Device
- ADR-0002: Device Registry as the Single Source of Truth
- Device Lifecycle Specification
