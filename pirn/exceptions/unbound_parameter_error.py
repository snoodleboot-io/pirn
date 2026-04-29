from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class UnboundParameterError(PirnError):
    """Raised when a Parameter has no value and no default at resolve time."""
