"""``ConversationThread`` — a durable, session-keyed multi-turn conversation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.conversation_turn import ConversationTurn


@dataclass(frozen=True)
class ConversationThread(PirnOpaqueValue):
    """An ordered, session-keyed sequence of conversation turns.

    A thread is a frozen value that round-trips through :meth:`to_payload` /
    :meth:`from_payload`, so it persists across process restarts under a stable
    ``session_id``. :meth:`append` returns a new thread with the next turn added.

    Attributes
    ----------
    session_id:
        Stable id keying this thread's durable state. Non-empty.
    turns:
        The ordered conversation turns.
    """

    session_id: str
    turns: tuple[ConversationTurn, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TypeError("ConversationThread: session_id must be a non-empty str")

    def append(self, *, role: str, content: str) -> ConversationThread:
        """Return a new thread with a turn (auto-indexed) appended."""
        turn = ConversationTurn(index=len(self.turns), role=role, content=content)
        return ConversationThread(session_id=self.session_id, turns=(*self.turns, turn))

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of the whole thread."""
        return {
            "session_id": self.session_id,
            "turns": [turn.to_payload() for turn in self.turns],
        }

    @classmethod
    def from_payload(cls, payload: Any) -> ConversationThread:
        """Reconstruct a thread from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ConversationThread.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw: Sequence[Any] = payload.get("turns", ())
        return cls(
            session_id=str(payload["session_id"]),
            turns=tuple(ConversationTurn.from_payload(t) for t in raw),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
