"""``MapTypeError`` — raised when a mapped input receives a collection of the wrong type."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class MapTypeError(PirnError, TypeError):
    """Raised when a mapped input receives a collection of the wrong type.

    A ``PirnError`` like every other framework failure, and a ``TypeError``
    because the fault is the type of the collection a ``Map``/``ZipMap``/
    ``DictMap`` input resolved to.
    """
