from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class TapestryError(PirnError):
    """Raised for invalid Tapestry usage (empty run, unknown emitter, etc.)."""
