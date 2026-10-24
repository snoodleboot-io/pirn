"""``ResumedRunFrame`` — run-level facts of a session resume."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ResumedRunFrame(PirnOpaqueValue):
    """Whether a session's run chain was found, and how many turns it held.

    The frame half of the ``Payload[ResumedRunFrame, RunState | None]`` split
    (PIR-868, PIR-874).

    Attributes
    ----------
    session_id:
        The session that was resumed.
    found:
        Whether a run chain existed for ``session_id``.
    turn_count:
        How many turns ``RunState.from_chain`` consumed (``0`` when not found).
    """

    session_id: str
    found: bool
    turn_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "found": self.found,
            "turn_count": self.turn_count,
        }
