"""Value types used across the agent knots.

These are pure-Python values that flow through the agent pipeline: messages,
conversation windows, plans, tool calls, tool results, and final responses.
None of them carry engine state. The two boundary types with lineage
metadata — :class:`~pirn_agents.types.messaging.agent_response.AgentResponse`
and
:class:`~pirn_agents.types.messaging.conversation_payload.ConversationPayload`
— are core's ``Payload[Frame, Data]`` (ADR agents-speaks-core WS6b) and
content-address via ``_pirn_audit_dict()``; the rest are frozen dataclasses
that hash-equal naturally.
"""

__all__: list[str] = []
