"""``ContextBuilder`` — assemble messages plus optional system prompt into ``AgentContext``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage


class ContextBuilder(Knot):
    """Builds an :class:`AgentContext` from a sequence of messages.

    If ``system_prompt`` is supplied it is prepended to the message
    tuple as a ``system``-role :class:`AgentMessage` so downstream
    knots see it through the standard message channel.
    """

    def __init__(
        self,
        *,
        messages: Knot,
        _config: KnotConfig,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> None:
        if system_prompt is not None and not isinstance(system_prompt, str):
            raise TypeError(
                "ContextBuilder: system_prompt must be a string or None, "
                f"got {type(system_prompt).__name__}"
            )
        if isinstance(system_prompt, str) and not system_prompt:
            raise ValueError(
                "ContextBuilder: system_prompt must be non-empty when provided"
            )
        super().__init__(
            messages=messages,
            system_prompt=system_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        system_prompt: str | None = None,
        **_: Any,
    ) -> AgentContext:
        """Assemble a sequence of messages and an optional system prompt into an AgentContext.

        Args:
            messages: The ordered sequence of agent messages to include.
            system_prompt: Optional system instruction prepended as a system-role message.

        Returns:
            An AgentContext containing the ordered messages with optional system prefix.

        Raises:
            TypeError: If messages is not a sequence or any element is not an AgentMessage.
        """
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            raise TypeError(
                "ContextBuilder: messages must be a sequence, "
                f"got {type(messages).__name__}"
            )
        ordered = tuple(messages)
        for index, message in enumerate(ordered):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"ContextBuilder: messages[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
        if system_prompt:
            system_message = AgentMessage(role="system", content=system_prompt)
            ordered = (system_message, *ordered)
        return AgentContext(messages=ordered)
