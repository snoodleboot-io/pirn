"""Messaging value types: agent messages, conversation windows, and responses.

Value types that flow between the caller and the agent runtime:
:class:`~pirn_agents.types.messaging.agent_message.AgentMessage` (a frozen
value, hash-equal by content), the
:class:`~pirn_agents.types.messaging.conversation_payload.ConversationPayload`
conversation window (``Payload[ConversationFrame, tuple[AgentMessage, ...]]``),
and the final :class:`~pirn_agents.types.messaging.agent_response.AgentResponse`
(``Payload[GenerationFrame, str]``). ``AgentContext`` is the deprecated
pre-ADR name for ``ConversationPayload`` (ADR agents-speaks-core WS6b).
"""

__all__: list[str] = []
