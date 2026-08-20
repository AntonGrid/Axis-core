"""Pytest fixtures for the Axis Core test suite.

- Resets the in-memory registries/attestation stores before every test so
  tests are isolated (the oracle now tracks used nonces and devices).
- Configures ``ORACLE_SECRET_KEY`` so the whole suite runs in strict mode:
  attestations are signed by a real oracle Ed25519 key, not a stub.
"""
import base64

import pytest
from nacl.signing import SigningKey

from axis_core import oracle_storage
from axis_core.services import provisioning_service

#: A fixed oracle key for the test run. Its public key can be derived via
#: ``axis_core.oracle_keys.encode_oracle_public_key`` to verify signatures.
ORACLE_KEY = SigningKey.generate()


@pytest.fixture(autouse=True)
def _reset_axis_state(monkeypatch):
    provisioning_service._DB.clear()
    oracle_storage._ATTESTATIONS.clear()
    oracle_storage._REQUESTS.clear()
    oracle_storage._USED_NONCES.clear()
    monkeypatch.setenv(
        "ORACLE_SECRET_KEY",
        base64.b64encode(bytes(ORACLE_KEY)).decode("ascii"),
    )
    monkeypatch.delenv("AXIS_ALLOW_MOCK", raising=False)
    yield


@pytest.fixture
def oracle_key() -> SigningKey:
    """The Ed25519 signing key the oracle uses during the test run."""
    return ORACLE_KEY
