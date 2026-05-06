"""A single conversational turn flowing through an agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class AgentMessage(PirnOpaqueValue):
    """One message within an agent conversation.

    Attributes
    ----------
    role:
        Who produced the message (e.g. ``"user"``, ``"assistant"``,
        ``"system"``, ``"tool"``).
    content:
        The message body as plain text.
    name:
        Optional name of the tool or sub-agent that produced the
        message.
    tool_call_id:
        Set when ``role == "tool"`` to correlate the message with the
        tool invocation it answers.
    created_at:
        UTC instant the message was produced.
    """

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "created_at": self.created_at.isoformat(),
        }
