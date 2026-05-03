"""``ConstitutionalViolationError`` — raised when principles cannot be satisfied."""

from __future__ import annotations


class ConstitutionalViolationError(Exception):
    """Raised when violations persist after the maximum number of revision attempts."""
