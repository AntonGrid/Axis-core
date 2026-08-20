"""Runtime configuration for Axis Core.

These are protocol-level security parameters that govern the oracle's
acceptance of device proofs. They are kept in a single module so they can be
audited and tuned together (see ``docs/conformance.md``).
"""
import os

#: Maximum accepted proof age in seconds. Proofs older than this are rejected
#: with reason ``stale_timestamp``.
MAX_PROOF_AGE_SECONDS = 900

#: Maximum allowed future clock skew in seconds. Timestamps further in the
#: future are rejected with reason ``future_timestamp``.
MAX_CLOCK_SKEW_SECONDS = 300


def mock_mode_enabled() -> bool:
    """Whether the dev-only ``mock`` signature algorithm is accepted.

    Enabled via the ``AXIS_ALLOW_MOCK`` environment variable (``1``/``true``/
    ``yes``). By default the oracle REQUIRES real ``ed25519`` signatures.
    """
    return os.environ.get("AXIS_ALLOW_MOCK", "").strip().lower() in {"1", "true", "yes"}
