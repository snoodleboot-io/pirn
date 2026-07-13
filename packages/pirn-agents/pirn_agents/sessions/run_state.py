"""``RunState`` — the serialisable snapshot of an agent run at a safe point."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult


@dataclass(frozen=True)
class RunState(PirnOpaqueValue):
    """A round-trippable checkpoint of a run: messages, plan, tool results, cursor.

    The value is keyed by ``session_id`` and carries everything needed to resume:
    the ``messages`` accumulated so far, the ordered ``plan`` steps, the
    ``tool_results`` produced, and the :class:`ExecutionCursor` marking how far
    the plan has been executed. It round-trips through :meth:`to_payload` /
    :meth:`from_payload` with no data loss.

    Attributes
    ----------
    session_id:
        Stable id keying this run's durable state.
    messages:
        The ordered message history.
    plan:
        The ordered plan step labels.
    tool_results:
        The tool results produced so far.
    cursor:
        The execution cursor (how many plan steps are complete).
    """

    session_id: str
    messages: tuple[SessionMessage, ...] = field(default_factory=tuple)
    plan: tuple[str, ...] = field(default_factory=tuple)
    tool_results: tuple[SessionToolResult, ...] = field(default_factory=tuple)
    cursor: ExecutionCursor = field(default_factory=ExecutionCursor)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TypeError("RunState: session_id must be a non-empty str")
        if not isinstance(self.cursor, ExecutionCursor):
            raise TypeError(
                f"RunState: cursor must be an ExecutionCursor, got {type(self.cursor).__name__}"
            )

    def remaining_plan(self) -> tuple[str, ...]:
        """Return the uncomputed tail of the plan (steps past the cursor)."""
        return self.plan[self.cursor.step_index :]

    def with_message(self, message: SessionMessage) -> RunState:
        """Return a new state with ``message`` appended to the history."""
        return RunState(
            session_id=self.session_id,
            messages=(*self.messages, message),
            plan=self.plan,
            tool_results=self.tool_results,
            cursor=self.cursor,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping capturing the whole run state."""
        return {
            "session_id": self.session_id,
            "messages": [m.to_payload() for m in self.messages],
            "plan": list(self.plan),
            "tool_results": [r.to_payload() for r in self.tool_results],
            "cursor": self.cursor.to_payload(),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> RunState:
        """Reconstruct a run state from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"RunState.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        messages: Sequence[Any] = payload.get("messages", ())
        results: Sequence[Any] = payload.get("tool_results", ())
        plan: Sequence[Any] = payload.get("plan", ())
        return cls(
            session_id=str(payload["session_id"]),
            messages=tuple(SessionMessage.from_payload(m) for m in messages),
            plan=tuple(str(step) for step in plan),
            tool_results=tuple(SessionToolResult.from_payload(r) for r in results),
            cursor=ExecutionCursor.from_payload(payload.get("cursor", {})),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
