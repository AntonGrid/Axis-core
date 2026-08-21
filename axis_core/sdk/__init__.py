"""Axis Core SDK — a thin client for the reference oracle/registry service.

The SDK lets devices and integrators speak the Axis Protocol without touching
the wire format directly:

- build and sign **Trust Envelopes** (``axis_core.wire``);
- register devices with proof-of-possession;
- submit proofs and read attestations;
- read device records from the Registry.

It is transport-agnostic: the default transport is HTTP(S) via ``httpx``,
but any callable with the same signature can be injected (used by the tests
to avoid network access).
"""

from axis_core.sdk.client import AxisClient, HttpError

__all__ = ["AxisClient", "HttpError"]
