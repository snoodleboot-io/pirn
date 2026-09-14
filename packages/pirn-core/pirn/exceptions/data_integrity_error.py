from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class DataIntegrityError(PirnError, ValueError):
    """Raised when a stored value fails its HMAC signature check.

    Subclasses ``ValueError`` in addition to ``PirnError`` — matching the
    precedent set by :class:`~pirn.exceptions.value_evicted_error.ValueEvictedError`
    subclassing ``KeyError`` — because every existing caller of
    :meth:`~pirn.backends.signer.Signer.verify` catches ``ValueError`` for
    a truncated or tampered payload.
    """
