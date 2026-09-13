from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class PirnConfigError(PirnError, ValueError):
    """Raised when pirn configuration is missing or invalid.

    Subclasses ``ValueError`` in addition to ``PirnError`` — matching the
    precedent set by :class:`~pirn.exceptions.value_evicted_error.ValueEvictedError`
    subclassing ``KeyError`` — because every existing caller of
    :meth:`~pirn.backends._signer._Signer.from_env` catches ``ValueError``
    for a missing or malformed signing key.
    """
