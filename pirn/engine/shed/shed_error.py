from __future__ import annotations


class ShedError(Exception):
    """Raised for structural problems found during shed derivation
    (cycles, id collisions, etc.).  Setup-time errors, allowed to propagate."""
