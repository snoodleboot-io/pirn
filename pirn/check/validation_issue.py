from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationIssue:
    severity: str  # "error" or "warning"
    knot_id: str | None
    message: str

    def __str__(self) -> str:
        loc = f"[{self.knot_id}] " if self.knot_id else ""
        return f"{self.severity.upper()}: {loc}{self.message}"
