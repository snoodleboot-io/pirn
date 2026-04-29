from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class DuplicateKnotError(PirnError):
    """Raised when a knot is registered more than once in a backend."""
