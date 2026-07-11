"""``AnthropicMessagesProvider`` — LLM provider for the Messages API wire format.

A first-class :class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider`
subclass for a provider whose request/response shape differs from
chat-completions, added as an equal peer to balance the OpenAI-compatible
adapter. It demonstrates the base's provider-neutrality: only request-shaping
and response-parsing differ.

Distinct-shape specifics handled here:

* ``system`` messages are hoisted out of ``messages`` into a top-level
  ``system`` field; ``max_tokens`` is required (defaulted when unset).
* responses carry ``content`` *blocks* (text + ``tool_use``); ``stop_reason``
  maps to a neutral finish reason; usage exposes ``cache_read_input_tokens``.
* streaming uses typed SSE events (``message_start``/``content_block_*``/
  ``message_delta``) rather than chat-completions chunks.
* prompt caching is natively supported: the opt-in hook adds ``cache_control``
  to the system prompt (a genuine, non-no-op override).

The HTTP client (``httpx``) is imported lazily by the base class; install with
``pip install "pirn-agents[web]"``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.llm.anthropic_messages_tool_adapter import AnthropicMessagesToolAdapter
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.toolset import Toolset


class AnthropicMessagesProvider(BaseLLMProvider):
    """Provider speaking the Messages API HTTP wire format."""

    def _tool_adapter(self) -> ProviderAdapter:
        return AnthropicMessagesToolAdapter()

    def _completions_path(self) -> str:
        return "/messages"

    def _auth_headers(self) -> dict[str, str]:
        headers = {"anthropic-version": "2023-06-01"}
        if self._credential is not None:
            headers["x-api-key"] = self._credential.reveal()
        return headers

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
        system_parts: list[str] = []
        conversation: list[dict[str, Any]] = []
        for message in messages:
            if message.get("role") == "system":
                system_parts.append(str(message.get("content", "")))
                continue
            conversation.append({"role": message.get("role"), "content": message.get("content")})
        resolved_max_tokens = max_tokens if max_tokens is not None else self._default_max_tokens
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": conversation,
            "max_tokens": resolved_max_tokens if resolved_max_tokens is not None else 1024,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        if temperature is not None:
            payload["temperature"] = temperature
        if tools is not None and len(tools) > 0:
            payload["tools"] = self._codec.encode_tools(tools)
        return payload

    def _apply_prompt_cache(self, payload: dict[str, Any]) -> None:
        """Attach ``cache_control`` to the system prompt when caching is on.

        A genuine (non-no-op) override: when ``enable_prompt_cache`` is set and
        a ``system`` prompt is present, it is converted into a cache-marked
        text block so the provider can reuse the context across calls. When the
        flag is off, the request shape is left untouched.
        """
        if not self._enable_prompt_cache:
            return None
        system = payload.get("system")
        if isinstance(system, str) and system:
            payload["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        return None

    def _content_text(self, data: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    def _tool_message(self, data: Mapping[str, Any]) -> Any:
        return data

    def _finish_reason(self, data: Mapping[str, Any]) -> str:
        return self._map_stop_reason(data.get("stop_reason"))

    def _usage_tokens(self, data: Mapping[str, Any]) -> dict[str, int]:
        return self._normalise_usage(data.get("usage"))

    async def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        tool_indices: set[int] = set()
        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            body = line[len("data:") :].strip()
            if not body:
                continue
            event = json.loads(body)
            if event.get("type") == "content_block_start":
                block = event.get("content_block") or {}
                if block.get("type") == "tool_use":
                    tool_indices.add(int(event.get("index", 0)))
            delta = self._stream_event_to_delta(event, tool_indices)
            if delta is not None:
                yield delta

    def _stream_event_to_delta(
        self, event: Mapping[str, Any], tool_indices: set[int]
    ) -> StreamDelta | None:
        event_type = event.get("type")
        if event_type == "message_start":
            usage_raw = (event.get("message") or {}).get("usage")
            if usage_raw:
                return StreamDelta(usage=self._normalise_usage(usage_raw))
            return None
        if event_type == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                return StreamDelta(
                    tool_call={
                        "index": event.get("index", 0),
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "arguments": "",
                    }
                )
            return None
        if event_type == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                return StreamDelta(content=str(delta.get("text", "")))
            if delta.get("type") == "input_json_delta":
                return StreamDelta(
                    tool_call={
                        "index": event.get("index", 0),
                        "arguments": str(delta.get("partial_json", "")),
                    }
                )
            return None
        if event_type == "content_block_stop":
            # Only tool_use blocks complete a streamed tool call; text blocks
            # carry no tool-call state and must not be flushed as one.
            index = int(event.get("index", 0))
            if index not in tool_indices:
                return None
            return StreamDelta(tool_call={"index": index, "arguments": "", "done": True})
        if event_type == "message_delta":
            stop = (event.get("delta") or {}).get("stop_reason")
            usage_raw = event.get("usage")
            return StreamDelta(
                finish_reason=self._map_stop_reason(stop) if stop is not None else None,
                usage=self._normalise_usage(usage_raw) if usage_raw else None,
            )
        return None

    @staticmethod
    def _map_stop_reason(stop_reason: Any) -> str:
        mapping = {"end_turn": "stop", "max_tokens": "length", "tool_use": "tool_use"}
        if isinstance(stop_reason, str):
            return mapping.get(stop_reason, stop_reason)
        return "stop"

    @staticmethod
    def _normalise_usage(usage_raw: Any) -> dict[str, int]:
        # Only surface fields actually present: streaming reports input tokens
        # on ``message_start`` and output tokens on ``message_delta``, so a fixed
        # ``0`` default would clobber the earlier value when the two are merged.
        usage: Mapping[str, Any] = usage_raw if isinstance(usage_raw, Mapping) else {}
        normalised: dict[str, int] = {}
        if "input_tokens" in usage:
            normalised["input_tokens"] = int(usage.get("input_tokens", 0))
        if "output_tokens" in usage:
            normalised["output_tokens"] = int(usage.get("output_tokens", 0))
        if "cache_read_input_tokens" in usage:
            normalised["cached_input_tokens"] = int(usage.get("cache_read_input_tokens", 0))
        return normalised
