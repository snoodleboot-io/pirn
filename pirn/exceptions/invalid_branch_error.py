from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class InvalidBranchError(PirnError):
    """Raised when a Branch selector returns an undeclared branch name."""
