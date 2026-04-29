from __future__ import annotations


class _GateClosed(Exception):
    """Internal signal: the gate predicate returned False."""
