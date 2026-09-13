from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class TapestryError(PirnError, ValueError):
    """Raised for invalid Tapestry usage (empty run, unknown emitter, etc.).

    Subclasses ``ValueError`` in addition to ``PirnError`` — matching the
    precedent set by :class:`~pirn.exceptions.value_evicted_error.ValueEvictedError`
    subclassing ``KeyError`` — because every existing caller of
    :class:`~pirn.tapestry.Tapestry` catches ``ValueError`` for these usage
    errors.
    """
