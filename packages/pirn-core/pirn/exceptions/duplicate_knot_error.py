from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class DuplicateKnotError(PirnError, ValueError):
    """Raised when a different Knot instance is registered under an id already in use.

    Subclasses ``ValueError`` in addition to ``PirnError`` — matching the
    precedent set by :class:`~pirn.exceptions.value_evicted_error.ValueEvictedError`
    subclassing ``KeyError`` — because every ``TapestryStore`` implementation's
    existing callers catch ``ValueError`` for a duplicate registration.
    """
