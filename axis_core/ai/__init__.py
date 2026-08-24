"""AI signal layer — Phase 0 scaffold (ENRG-AI integration).

Per ADR-0003 the AI oracle is a **source of signals, not decisions**.
This package produces verifiable observations (anomaly, forecast, market)
that the Policy Engine **may** consume. A signal never blocks or mints by
itself: the decision belongs to ``axis_core.policy``.

Phase 0 ships a neutral ``SignalProvider`` stub so the oracle can be wired
up without changing behavior. Phase 1 (``anomaly``, ``forecast``) and
Phase 3 (``market``) fill in real signal sources.
"""

from axis_core.ai.signal_provider import Signal, SignalProvider

__all__ = ["Signal", "SignalProvider"]
