from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ShedError(PirnError):
    """Raised for structural problems found during shed derivation
    (cycles, id collisions, etc.).  Setup-time errors, allowed to propagate."""
