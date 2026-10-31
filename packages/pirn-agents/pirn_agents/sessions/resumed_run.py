"""``ResumedRun`` — the outcome of rehydrating a session from its run chain.

ADR agents-speaks-core WS6b: a value crossing a knot boundary is a
``Payload[Frame, Data]``. ``RunResumer`` used to return ``RunState | None``;
PIR-874 (following PIR-868) wraps it at the producer. ``RunState`` is a JSON
read model and is unchanged: it is the ``data`` (``None`` when no run exists),
while the frame (:class:`~pirn_agents.sessions.resumed_run_frame.ResumedRunFrame`)
holds the run-level facts (session id, ``found``, ``turn_count``).

``sessions/`` must not import from ``specializations/``, so this subclasses
:class:`pirn.core.payload.Payload` directly and adds the same structural
``__eq__`` that ``AgentResult`` carries.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload

from pirn_agents.sessions.resumed_run_frame import ResumedRunFrame
from pirn_agents.sessions.run_state import RunState


class ResumedRun(Payload[ResumedRunFrame, RunState | None]):
    """A session's rehydrated :class:`RunState`, or ``None`` data when absent."""

    def __init__(
        self,
        *,
        session_id: str,
        state: RunState | None,
        turn_count: int,
    ) -> None:
        frame = ResumedRunFrame(
            session_id=session_id,
            found=state is not None,
            turn_count=turn_count,
        )
        super().__init__(metadata=frame, data=state)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["state"] = self.data.to_payload() if self.data is not None else None
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
