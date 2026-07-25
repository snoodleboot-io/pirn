"""``OpenAICompatibleProvider`` — LLM provider for the chat-completions wire format.

A thin :class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider` subclass that
supplies request-shaping and response-parsing for the widely-implemented
``POST {base_url}/chat/completions`` protocol. A single adapter therefore
serves self-hosted engines (vLLM, Ollama), OpenAI-compatible gateways, and
hosted endpoints without privileging any of them — the only difference is the
configured ``base_url``/``model``/api key.

The HTTP client (``httpx``) is imported lazily by the base class, so this
module is import-safe with no backend installed; install it with
``pip install "pirn-agents[web]"``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.multimodal_adapter import MultimodalAdapter
from pirn_agents.llm.openai_compatible_multimodal_adapter import (
    OpenAICompatibleMultimodalAdapter,
)
from pirn_agents.llm.openai_compatible_tool_adapter import OpenAICompatibleToolAdapter
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.toolset import Toolset


class OpenAICompatibleProvider(BaseLLMProvider):
    """Provider speaking the ``chat/completions`` HTTP wire format."""

    def _tool_adapter(self) -> ProviderAdapter:
        return OpenAICompatibleToolAdapter()

    def _multimodal_adapter(self) -> MultimodalAdapter:
        return OpenAICompatibleMultimodalAdapter()

    # -- structured output (F20) ----------------------------------------

    def structured_output_capability(self) -> StructuredOutputCapability:
        """Advertise native schema, forced tool-choice, and constrained decoding.

        The ``chat/completions`` wire format carries ``response_format`` (JSON
        schema) and ``tool_choice``; the self-hosted engines this adapter also
        serves (vLLM/Ollama) accept guided-decoding constraints via
        ``extra_body``. All three native single-pass paths are therefore
        available.
        """
        return StructuredOutputCapability(
            native_schema=True, forced_tool_choice=True, constrained_decoding=True
        )

    def native_schema_option(self, schema: Mapping[str, Any], *, name: str) -> Mapping[str, Any]:
        """Shape a ``response_format`` JSON-schema fragment for the request."""
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": dict(schema), "strict": True},
            }
        }

    def forced_tool_choice_option(self, tool_name: str) -> Mapping[str, Any]:
        """Shape a ``tool_choice`` fragment forcing ``tool_name``."""
        return {"tool_choice": {"type": "function", "function": {"name": tool_name}}}

    def constrained_decoding_option(self, constraint: Mapping[str, Any]) -> Mapping[str, Any]:
        """Shape guided-decoding fields under ``extra_body`` from a constraint."""
        extra_body: dict[str, Any] = {}
        json_schema = constraint.get("json_schema")
        if isinstance(json_schema, Mapping):
            extra_body["guided_json"] = dict(json_schema)
        regex = constraint.get("regex")
        if isinstance(regex, str):
            extra_body["guided_regex"] = regex
        grammar = constraint.get("grammar")
        if isinstance(grammar, str):
            extra_body["guided_grammar"] = grammar
        return {"extra_body": extra_body}

    def _completions_path(self) -> str:
        return "/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        if self._credential is None:
            return {}
        return {"Authorization": f"Bearer {self._credential.reveal()}"}

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
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [dict(message) for message in messages],
            "stream": stream,
        }
        resolved_max_tokens = max_tokens if max_tokens is not None else self._default_max_tokens
        if resolved_max_tokens is not None:
            payload["max_tokens"] = resolved_max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if tools is not None and len(tools) > 0:
            payload["tools"] = self._codec.encode_tools(tools)
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _content_text(self, data: Mapping[str, Any]) -> str:
        message = self._first_message(data)
        content = message.get("content")
        return content if isinstance(content, str) else ""

    def _tool_message(self, data: Mapping[str, Any]) -> Any:
        return self._first_message(data)

    def _finish_reason(self, data: Mapping[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return "stop"
        return choices[0].get("finish_reason") or "stop"

    def _usage_tokens(self, data: Mapping[str, Any]) -> dict[str, int]:
        return self._normalise_usage(data.get("usage"))

    async def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            body = line[len("data:") :].strip()
            if body == "[DONE]":
                break
            chunk = json.loads(body)
            choices = chunk.get("choices") or []
            delta_obj = choices[0].get("delta") or {} if choices else {}
            finish = choices[0].get("finish_reason") if choices else None
            usage_raw = chunk.get("usage")
            usage = self._normalise_usage(usage_raw) if usage_raw else None
            for tool_delta in delta_obj.get("tool_calls") or []:
                function = tool_delta.get("function") or {}
                yield StreamDelta(
                    tool_call={
                        "index": tool_delta.get("index", 0),
                        "id": tool_delta.get("id"),
                        "name": function.get("name"),
                        "arguments": function.get("arguments", ""),
                    }
                )
            content_piece = delta_obj.get("content")
            if content_piece or finish is not None or usage is not None:
                yield StreamDelta(
                    content=content_piece if isinstance(content_piece, str) else "",
                    finish_reason=finish,
                    usage=usage,
                )

    @staticmethod
    def _first_message(data: Mapping[str, Any]) -> Mapping[str, Any]:
        choices = data.get("choices") or []
        if not choices:
            return {}
        message = choices[0].get("message")
        return message if isinstance(message, Mapping) else {}

    @staticmethod
    def _normalise_usage(usage_raw: Any) -> dict[str, int]:
        usage: Mapping[str, Any] = usage_raw if isinstance(usage_raw, Mapping) else {}
        normalised: dict[str, int] = {
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
        }
        details = usage.get("prompt_tokens_details")
        if isinstance(details, Mapping) and "cached_tokens" in details:
            normalised["cached_input_tokens"] = int(details.get("cached_tokens", 0))
        return normalised
