"""``ExecutionCursor`` — how far a run has progressed through its plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ExecutionCursor(PirnOpaqueValue):
    """The execution position of a run through its plan.

    ``step_index`` is the number of plan steps already completed, so
    ``plan[step_index:]`` is the uncomputed tail a resume must replay.

    Attributes
    ----------
    step_index:
        Count of completed plan steps (0 = nothing done yet). Non-negative.
    completed_steps:
        The ids/labels of steps already executed, in order.
    """

    step_index: int = 0
    completed_steps: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.step_index, bool) or not isinstance(self.step_index, int):
            raise TypeError("ExecutionCursor: step_index must be an int")
        if self.step_index < 0:
            raise ValueError(f"ExecutionCursor: step_index must be >= 0, got {self.step_index}")

    def advanced(self, step: str) -> ExecutionCursor:
        """Return a new cursor with ``step`` appended and the index incremented."""
        return ExecutionCursor(
            step_index=self.step_index + 1,
            completed_steps=(*self.completed_steps, step),
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this cursor."""
        return {"step_index": self.step_index, "completed_steps": list(self.completed_steps)}

    @classmethod
    def from_payload(cls, payload: Any) -> ExecutionCursor:
        """Reconstruct a cursor from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ExecutionCursor.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw: Sequence[Any] = payload.get("completed_steps", ())
        return cls(
            step_index=int(payload.get("step_index", 0)),
            completed_steps=tuple(str(s) for s in raw),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
