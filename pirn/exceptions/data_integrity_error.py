from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class DataIntegrityError(PirnError):
    """Raised when a stored value fails its HMAC signature check."""
