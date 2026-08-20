"""Deprecated re-export of the EVM domain adapter.

Use :mod:`axis_core.adapters.evm` directly instead:
``from axis_core.adapters.evm import build_attestation_params``.

This module is kept only for backward compatibility with existing imports.
"""
from axis_core.adapters.evm import *  # noqa: F401,F403
from axis_core.adapters.evm import (  # noqa: F401
    OnchainAttestationParams,
    _parse_issued_at,
    _to_bytes32_hash,
    build_attestation_params,
)
