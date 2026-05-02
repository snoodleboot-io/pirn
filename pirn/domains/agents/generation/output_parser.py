"""``OutputParser`` — coerce a raw LLM response mapping into an :class:`AgentResponse`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall


class OutputParser(Knot):
    """Parses a chat-completion mapping into an :class:`AgentResponse`.

    Recognises the common Anthropic / OpenAI shapes:

    * ``{"content": "<text>", "stop_reason": "...", "usage": {...}}``
    * ``{"content": [{"type": "text", "text": "..."}, ...], ...}``
    * ``{"choices": [{"message": {"content": "..."}, "finish_reason": "..."}]}``

    Tool-call entries (``type == "tool_use"``) are surfaced as
    :class:`ToolCall`s on the resulting response.
    """

    def __init__(
        self,
        *,
        response: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: Mapping[str, Any],
        **_: Any,
    ) -> AgentResponse:
        if not isinstance(response, Mapping):
            raise TypeError(
                "OutputParser: response must be a Mapping, "
                f"got {type(response).__name__}"
            )
        content_text, tool_calls = self._extract_content(response)
        finish_reason = self._extract_finish_reason(response)
        usage = self._extract_usage(response)
        return AgentResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    def _extract_content(
        self,
        response: Mapping[str, Any],
    ) -> tuple[str, tuple[ToolCall, ...]]:
        content = response.get("content")
        if isinstance(content, str):
            return content, ()
        if isinstance(content, list):
            return self._coerce_blocks(content)
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, Mapping):
                message = first.get("message")
                if isinstance(message, Mapping):
                    inner = message.get("content")
                    if isinstance(inner, str):
                        return inner, ()
        raise ValueError(
            "OutputParser: response did not contain a recognisable "
            "'content' or 'choices' field"
        )

    def _coerce_blocks(
        self,
        blocks: list[Any],
    ) -> tuple[str, tuple[ToolCall, ...]]:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif block_type == "tool_use":
                call_id = block.get("id") or block.get("call_id") or ""
                tool_name = block.get("name") or ""
                arguments = block.get("input") or block.get("arguments") or {}
                if isinstance(arguments, Mapping):
                    tool_calls.append(
                        ToolCall(
                            tool_name=str(tool_name),
                            arguments=dict(arguments),
                            call_id=str(call_id),
                        )
                    )
        return "".join(text_parts), tuple(tool_calls)

    def _extract_finish_reason(self, response: Mapping[str, Any]) -> str:
        for key in ("stop_reason", "finish_reason"):
            value = response.get(key)
            if isinstance(value, str) and value:
                return value
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, Mapping):
                value = first.get("finish_reason")
                if isinstance(value, str) and value:
                    return value
        return "stop"

    def _extract_usage(self, response: Mapping[str, Any]) -> Mapping[str, int]:
        usage = response.get("usage")
        if not isinstance(usage, Mapping):
            return {}
        primitive: dict[str, int] = {}
        for key, value in usage.items():
            if isinstance(value, int):
                primitive[str(key)] = value
        return primitive
