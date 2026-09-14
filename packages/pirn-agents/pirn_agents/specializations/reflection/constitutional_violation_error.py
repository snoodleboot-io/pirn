"""``ConstitutionalViolationError`` — raised when principles cannot be satisfied."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ConstitutionalViolationError(PirnError):
    """Raised when violations persist after the maximum number of revision attempts."""
