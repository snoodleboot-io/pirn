"""``HumanDecision`` — the operator's verdict injected on resume."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class HumanDecision(PirnOpaqueValue):
    """A human operator's approval decision, injected into a suspended run.

    Attributes
    ----------
    approved:
        Whether the operator approved the paused action.
    note:
        Optional free-text rationale.
    decided_by:
        Optional id of the operator who decided.
    """

    approved: bool
    note: str | None = None
    decided_by: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise TypeError(
                f"HumanDecision: approved must be a bool, got {type(self.approved).__name__}"
            )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this decision."""
        return {"approved": self.approved, "note": self.note, "decided_by": self.decided_by}

    @classmethod
    def from_payload(cls, payload: Any) -> HumanDecision:
        """Reconstruct a decision from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"HumanDecision.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        note = payload.get("note")
        decided_by = payload.get("decided_by")
        return cls(
            approved=bool(payload["approved"]),
            note=str(note) if note is not None else None,
            decided_by=str(decided_by) if decided_by is not None else None,
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
