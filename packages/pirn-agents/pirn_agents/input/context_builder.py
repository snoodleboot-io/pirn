"""``ContextBuilder`` — assemble messages plus optional system prompt into ``ConversationPayload``.

Algorithm:
    1. Receive the resolved messages sequence and optional system prompt.
    2. Validate types at process time.
    3. If ``system_prompt`` is provided, prepend a system-role ``AgentMessage``.
    4. Return the assembled ``ConversationPayload``.


References:
    - :class:`pirn_agents.types.messaging.conversation_payload.ConversationPayload`
    - :class:`pirn_agents.types.messaging.agent_message.AgentMessage`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


class ContextBuilder(Knot):
    """Builds a :class:`ConversationPayload` from a sequence of messages.

    If ``system_prompt`` is supplied it is prepended to the message
    tuple as a ``system``-role :class:`AgentMessage` so downstream
    knots see it through the standard message channel.
    """

    def __init__(
        self,
        *,
        messages: Knot,
        _config: KnotConfig,
        system_prompt: Knot | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            system_prompt=system_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: ConversationPayload,
        system_prompt: str | None = None,
        **_: Any,
    ) -> ConversationPayload:
        """Prepend an optional system prompt to a conversation window.

        Args:
            messages: The conversation window to build on.
            system_prompt: Optional system instruction prepended as a system-role message.

        Returns:
            ``messages`` derived with the system message in front when one is
            given — the same ``ConversationFrame`` carried forward — else
            ``messages`` unchanged (ADR agents-speaks-core WS6b; PIR-874).

        Raises:
            TypeError: If ``messages`` is not a ``ConversationPayload`` or
                ``system_prompt`` is neither a string nor ``None``.
            ValueError: If ``system_prompt`` is an empty string.
        """
        if not isinstance(messages, ConversationPayload):
            raise TypeError(
                "ContextBuilder: messages must be a ConversationPayload, "
                f"got {type(messages).__name__}"
            )
        if system_prompt is not None and not isinstance(system_prompt, str):
            raise TypeError(
                "ContextBuilder: system_prompt must be a string or None, "
                f"got {type(system_prompt).__name__}"
            )
        if isinstance(system_prompt, str) and not system_prompt:
            raise ValueError("ContextBuilder: system_prompt must be non-empty when provided")
        if not system_prompt:
            return messages
        system_message = AgentMessage(role="system", content=system_prompt)
        return messages.derive((system_message, *messages.data))
