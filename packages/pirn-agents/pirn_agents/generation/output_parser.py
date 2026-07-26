"""``OutputParser`` — coerce a raw LLM response mapping into an :class:`AgentResponse`.

Algorithm:
    1. Receive the resolved raw response mapping.
    2. Validate it is a Mapping at process time.
    3. Extract text content and tool calls from the response shape.
    4. Extract finish reason (``stop_reason`` / ``finish_reason`` / choices).
    5. Extract usage tokens if present.
    6. Return a typed :class:`AgentResponse`.


References:
    - Anthropic Messages API response format
    - OpenAI Chat Completions API response format
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.generation.content_block_handler import ContentBlockHandler
from pirn_agents.generation.text_block_handler import TextBlockHandler
from pirn_agents.generation.tool_use_block_handler import ToolUseBlockHandler
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.types.messaging.agent_response import AgentResponse


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
        """Parse a raw chat-completion mapping into a typed AgentResponse.

        Args:
            response: The raw mapping returned by the LLM provider.

        Returns:
            A typed AgentResponse with content, tool calls, finish reason, and usage extracted.

        Raises:
            TypeError: If response is not a Mapping.
            ValueError: If response contains no recognisable content or choices field.
        """
        if not isinstance(response, Mapping):
            raise TypeError(
                f"OutputParser: response must be a Mapping, got {type(response).__name__}"
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
            "OutputParser: response did not contain a recognisable 'content' or 'choices' field"
        )

    def _coerce_blocks(
        self,
        blocks: list[Any],
    ) -> tuple[str, tuple[ToolCall, ...]]:
        handlers = self._block_handlers()
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            for handler in handlers:
                contribution = handler.try_handle(block)
                if contribution is None:
                    continue
                if contribution.text is not None:
                    text_parts.append(contribution.text)
                if contribution.tool_call is not None:
                    tool_calls.append(contribution.tool_call)
                break
        return "".join(text_parts), tuple(tool_calls)

    @staticmethod
    def _block_handlers() -> tuple[ContentBlockHandler, ...]:
        """Return the ordered content-block handlers.

        Support for a new block ``type`` is a new :class:`ContentBlockHandler`
        subclass appended here — the loop in :meth:`_coerce_blocks` never
        changes (OCP).
        """
        return (TextBlockHandler(), ToolUseBlockHandler())

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
