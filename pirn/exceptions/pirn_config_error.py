from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class PirnConfigError(PirnError):
    """Raised when pirn configuration is missing or invalid."""
