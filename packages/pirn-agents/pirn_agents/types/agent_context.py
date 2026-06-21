"""The full conversational state passed between agent knots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.agent_message import AgentMessage


@dataclass(frozen=True)
class AgentContext(PirnOpaqueValue):
    """Conversation history plus a free-form metadata bag.

    Attributes
    ----------
    messages:
        Ordered tuple of :class:`AgentMessage` covering the
        conversation so far.
    metadata:
        Mapping for intermediate state shared between knots (parsed
        intents, retrieved memories, partial plans). Defaults to an
        empty dict.
    """

    messages: tuple[AgentMessage, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "messages": [m._pirn_audit_dict() for m in self.messages],
            "metadata": dict(self.metadata),
        }
