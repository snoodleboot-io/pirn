from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class BackendCapabilityError(PirnError, RuntimeError):
    """Raised when an installed backend lacks a capability the call requires.

    The dependency is present — this is not an :class:`ImportError` — but the
    version or object in hand cannot do what was asked: a ``pyedflib`` too old
    to expose any PHI-redaction setter, an injected SDK client with no request
    entry-point. Raised rather than degraded around, because every fallback
    here is silent harm: an unredacted PHI field written to disk, or a call
    that quietly never left the process.

    Subclasses ``RuntimeError`` in addition to ``PirnError`` so every existing
    ``except RuntimeError`` handler around a connector call keeps working
    unchanged, while new code can narrow to this specific failure.
    """
