"""``ConversationFrame`` — lineage metadata for a conversation window."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ConversationFrame(PirnOpaqueValue):
    """Lineage descriptor for a :class:`ConversationPayload`.

    Carries everything about *which conversation* a message window belongs
    to and *how much of it* remains, without carrying the messages
    themselves — the frame half of the
    ``Payload[ConversationFrame, tuple[AgentMessage, ...]]`` split (ADR
    agents-speaks-core WS6b).

    Attributes
    ----------
    session_id:
        Identifier of the session this conversation belongs to, or ``None``
        when the caller has not assigned one.
    turn_id:
        Identifier of the current turn within the session, or ``None``.
    token_count:
        Running token count for the messages carried by this payload.
        Defaults to ``0`` when not tracked.
    truncated:
        Whether earlier messages were dropped or summarised to fit a
        context budget. Defaults to ``False``.
    extra:
        Free-form bag for intermediate state shared between knots (parsed
        intents, retrieved memories, partial plans) that does not fit the
        structured fields above. Defaults to an empty mapping.
    """

    session_id: str | None = None
    turn_id: str | None = None
    token_count: int = 0
    truncated: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict[str, Any])

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "token_count": self.token_count,
            "truncated": self.truncated,
            "extra": dict(self.extra),
        }
