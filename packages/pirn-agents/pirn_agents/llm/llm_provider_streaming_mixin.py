"""``LLMProviderStreamingMixin`` — token/tool-call streaming for HTTP LLM providers.

Extracted from :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` (PIR-856,
SRP) to keep that orchestrator under one screenful of responsibility. This
mixin owns :meth:`stream_chat` (the raw unified :class:`StreamDelta` iterator),
:meth:`stream_response` (drains it into one :class:`AgentResponse`), and
:meth:`collect_stream` (the fold itself — content concatenation, tool-call
fragment assembly via :class:`StreamingToolCallParser`, last-writer-wins
finish reason/usage, and cost estimation).

It reads request-building and transport hooks
(``_build_request``/``_apply_prompt_cache``/``_get_client``/``_url``/
``_completions_path``/``_request_headers``/``_iter_stream``) and the
``_mapper`` collaborator from :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider`;
it contributes no ``__init__`` of its own and is always combined with that
base, never instantiated directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.tools.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tools.toolset import Toolset
from pirn_agents.types.messaging.agent_response import AgentResponse


class LLMProviderStreamingMixin:
    """Token/tool-call streaming surface for :class:`BaseLLMProvider`."""

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
    ) -> AsyncIterator[StreamDelta]:
        """Yield unified :class:`StreamDelta` fragments for ``messages``.

        Tokens are yielded as they arrive (before completion); tool calls
        arrive as incremental fragments. The underlying HTTP stream is always
        closed on exit — including consumer cancellation or a mid-stream
        error — via ``async with``, so no connection leaks.
        """
        payload = self._build_request(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            tools=tools,
        )
        self._apply_prompt_cache(payload)
        client = await self._get_client()
        url = self._url(self._completions_path())
        headers = self._request_headers()
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            status = int(response.status_code)
            if not 200 <= status < 300:
                raise LLMHTTPStatusError(f"stream failed with http {status}", status_code=status)
            async for delta in self._iter_stream(response):
                yield delta

    async def stream_response(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
    ) -> AgentResponse:
        """Drain :meth:`stream_chat` into a complete :class:`AgentResponse`."""
        return await self.collect_stream(
            self.stream_chat(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
        )

    async def collect_stream(self, deltas: AsyncIterable[StreamDelta]) -> AgentResponse:
        """Fold a stream of :class:`StreamDelta` into one :class:`AgentResponse`.

        Content fragments are concatenated; tool-call fragments are assembled
        into decodable :class:`~pirn_agents.tools.tool_call.ToolCall`s via
        :class:`StreamingToolCallParser`; the last non-``None`` finish reason
        and usage win; cost is estimated when pricing is configured.
        """
        content_parts: list[str] = []
        finish_reason = "stop"
        usage: dict[str, int] = {}
        tool_deltas: list[Mapping[str, Any]] = []
        async for delta in deltas:
            if delta.content:
                content_parts.append(delta.content)
            if delta.finish_reason is not None:
                finish_reason = delta.finish_reason
            if delta.usage is not None:
                usage = {**usage, **dict(delta.usage)}
            if delta.tool_call is not None:
                tool_deltas.append(delta.tool_call)

        async def _emit() -> AsyncIterator[Mapping[str, Any]]:
            for fragment in tool_deltas:
                yield fragment

        calls = tuple(await StreamingToolCallParser().parse_to_list(_emit()))
        return AgentResponse(
            content="".join(content_parts),
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=usage,
            cost=self._mapper.estimate_cost(usage),
        )
