"""Shared stub doubles for F20 structured-output / constrained-decoding tests.

``StubStructuredProvider`` is a capability-configurable LLM provider with a fake
transport: it records the structured requests it receives and returns a
scripted :class:`AgentResponse` (native/constrained content or a forced tool
call), plus a scripted plain-``chat`` script for the retry-pipeline fallback.
No real backend, no network — purely provider-neutral doubles.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_call import ToolCall


class StubStructuredProvider(StructuredOutputProvider):
    """A capability-gated structured-output provider with a recording transport."""

    def __init__(
        self,
        *,
        capability: StructuredOutputCapability,
        structured_response: AgentResponse | None = None,
        chat_responses: Sequence[str] = (),
    ) -> None:
        """Configure advertised capabilities and scripted responses.

        Args:
            capability: The flags advertised via
                :meth:`structured_output_capability`.
            structured_response: The :class:`AgentResponse` returned from every
                :meth:`structured_chat` call (native content or forced tool call).
            chat_responses: Scripted plain-``chat`` contents for the fallback
                retry pipeline.
        """
        self._capability = capability
        self._structured_response = structured_response
        self._chat_responses = list(chat_responses)
        self._chat_index = 0
        self.structured_calls: list[dict[str, Any]] = []
        self.chat_calls: list[Sequence[Mapping[str, Any]]] = []

    # -- structured-output surface --------------------------------------

    def structured_output_capability(self) -> StructuredOutputCapability:
        return self._capability

    async def structured_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Toolset | None = None,
        request_options: Mapping[str, Any] | None = None,
    ) -> AgentResponse:
        self.structured_calls.append(
            {
                "messages": [dict(message) for message in messages],
                "tools": tools,
                "request_options": dict(request_options) if request_options else None,
            }
        )
        if self._structured_response is None:
            raise AssertionError("StubStructuredProvider: no scripted structured_response")
        return self._structured_response

    def native_schema_option(self, schema: Mapping[str, Any], *, name: str) -> Mapping[str, Any]:
        return {"response_format": {"name": name, "schema": dict(schema)}}

    def forced_tool_choice_option(self, tool_name: str) -> Mapping[str, Any]:
        return {"tool_choice": {"name": tool_name}}

    def constrained_decoding_option(self, constraint: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"extra_body": {"constraint": dict(constraint)}}

    # -- plain LLMProvider surface (fallback pipeline) ------------------

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.chat_calls.append([dict(message) for message in messages])
        if self._chat_index < len(self._chat_responses):
            content = self._chat_responses[self._chat_index]
            self._chat_index += 1
        else:
            content = self._chat_responses[-1] if self._chat_responses else ""
        return {"role": "assistant", "content": content}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"content": "stub"}

        return _aiter()

    async def close(self) -> None:
        return None


def tool_call_response(
    arguments: Mapping[str, Any], *, tool_name: str = "extract"
) -> AgentResponse:
    """Build an :class:`AgentResponse` carrying a single forced tool call."""
    return AgentResponse(
        content="",
        tool_calls=(ToolCall(tool_name=tool_name, arguments=dict(arguments), call_id="c1"),),
        finish_reason="tool_use",
    )


def content_response(content: str) -> AgentResponse:
    """Build an :class:`AgentResponse` carrying native JSON content."""
    return AgentResponse(content=content)
