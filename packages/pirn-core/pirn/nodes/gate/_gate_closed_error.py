from __future__ import annotations


class _GateClosedError(Exception):
    """Internal signal: the gate predicate returned False."""
