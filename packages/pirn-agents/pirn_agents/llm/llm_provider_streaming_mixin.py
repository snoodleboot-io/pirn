"""``LLMProviderStreamingMixin`` — token/tool-call streaming for HTTP LLM providers.

Extracted from :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` (PIR-856,
SRP) to keep that orchestrator under one screenful of responsibility. This
mixin owns :meth:`stream_chat` (the raw unified :class:`StreamDelta` iterator),
:meth:`stream_response` (drains it into one :class:`AgentResponse`), and
:meth:`collect_stream` (the fold itself — content concatenation, tool-call
fragment assembly via :class:`StreamingToolCallParser`, last-writer-wins
finish reason/usage, and cost estimation).

It reads the pooled client from
:class:`~pirn.connectors.connector_base.ConnectorBase` (which it derives from),
declares the request-building and transport hooks it calls
(``_build_request``/``_apply_prompt_cache``/``_url``/``_completions_path``/
``_request_headers``/``_iter_stream``) as ``NotImplementedError`` methods that
:class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` overrides, and reads
its ``_mapper`` collaborator; it contributes no ``__init__`` of its own and is
always combined with that base, never instantiated directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.connectors.connector_base import ConnectorBase

from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.response_mapper import ResponseMapper
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.tools.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tools.toolset import Toolset
from pirn_agents.types.messaging.agent_response import AgentResponse


class LLMProviderStreamingMixin(ConnectorBase):
    """Token/tool-call streaming surface for :class:`BaseLLMProvider`."""

    # -- host collaborator this mixin reads (set by BaseLLMProvider.__init__) --
    _mapper: ResponseMapper

    # -- host hooks this mixin calls; BaseLLMProvider's own body overrides each --

    def _build_request(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        tools: Toolset | None,
    ) -> dict[str, Any]:
        """Shape a request body for this provider's wire format."""
        raise NotImplementedError(f"{type(self).__name__} must implement _build_request()")

    def _apply_prompt_cache(self, payload: dict[str, Any]) -> None:
        """Mutate ``payload`` to enable prompt/context caching, if supported."""
        raise NotImplementedError(f"{type(self).__name__} must implement _apply_prompt_cache()")

    def _url(self, path: str) -> str:
        """Join the configured base URL with ``path``."""
        raise NotImplementedError(f"{type(self).__name__} must implement _url()")

    def _completions_path(self) -> str:
        """Return the path (appended to ``base_url``) for chat completions."""
        raise NotImplementedError(f"{type(self).__name__} must implement _completions_path()")

    def _request_headers(self) -> dict[str, str]:
        """Return the merged base + provider-specific auth headers."""
        raise NotImplementedError(f"{type(self).__name__} must implement _request_headers()")

    def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        """Parse a streaming HTTP response into neutral :class:`StreamDelta`s."""
        raise NotImplementedError(f"{type(self).__name__} must implement _iter_stream()")

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

        calls = tuple(
            await StreamingToolCallParser().parse_to_list(
                LLMProviderStreamingMixin._replay_fragments(tool_deltas)
            )
        )
        return AgentResponse(
            content="".join(content_parts),
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=usage,
            cost=self._mapper.estimate_cost(usage),
        )

    @staticmethod
    async def _replay_fragments(
        fragments: Sequence[Mapping[str, Any]],
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Re-yield already-collected tool-call fragments as the async stream the parser reads."""
        for fragment in fragments:
            yield fragment
