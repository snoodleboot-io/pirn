"""Provider-neutral mapping between pirn tool-calling types and providers.

:class:`ToolCallCodec` orchestrates the round-trip of native tool calling
without embedding any provider-specific knowledge. It converts a
:class:`pirn_agents.toolset.Toolset` into native tool declarations, decodes
a provider's assistant message into :class:`pirn_agents.types.tool_call.ToolCall`
values, and encodes :class:`pirn_agents.types.tool_result.ToolResult` values
back into native tool-result messages.

Every provider-specific decision — the exact JSON shape of a tool
declaration, where tool calls live inside an assistant message, how a
tool result is framed — is delegated to a
:class:`pirn_agents.provider_adapter.ProviderAdapter`. Swapping providers
means swapping adapters; this module never changes and imports nothing
provider-specific. The only cross-provider convention it owns is that
"arguments-as-JSON" may arrive either as a JSON string or as an already
parsed mapping, handled with the stdlib :mod:`json` module.

The codec is opaque to pydantic (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity serialiser keeps content-addressing stable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult


class ToolCallCodec(PirnOpaqueValue):
    """Provider-neutral codec for native tool calling via an adapter."""

    def __init__(self, adapter: ProviderAdapter) -> None:
        """Bind the codec to the ``adapter`` doing provider-specific shaping.

        Args:
            adapter: The :class:`ProviderAdapter` that translates neutral
                shapes to and from one provider's native tool-calling JSON.
        """
        self._adapter: ProviderAdapter = adapter

    def encode_tools(self, toolset: Toolset) -> list[Any]:
        """Adapt a toolset's neutral schema into native tool declarations.

        Args:
            toolset: The tools to declare to the provider.

        Returns:
            One provider-native tool declaration per registered tool, in
            registration order.
        """
        return [self._adapter.tool_to_native(neutral) for neutral in toolset.schema()]

    def decode_calls(self, provider_msg: Any) -> list[ToolCall]:
        """Decode a provider assistant message into neutral tool calls.

        Handles single and parallel tool calls uniformly, and accepts
        arguments as either a JSON string or an already parsed mapping.

        Args:
            provider_msg: A provider-native assistant message.

        Returns:
            One :class:`ToolCall` per tool call, preserving order and the
            provider-native ``raw`` dict each was decoded from.
        """
        return [
            ToolCall(
                tool_name=raw["name"],
                arguments=self._parse_arguments(raw["arguments"]),
                call_id=raw["id"],
                raw=raw,
            )
            for raw in self._adapter.extract_tool_calls(provider_msg)
        ]

    def encode_results(self, results: Sequence[ToolResult]) -> list[Any]:
        """Encode tool results into native tool-result messages.

        The neutral content is the error string when the result carries an
        error, otherwise the produced value coerced to a JSON-safe form.

        Args:
            results: The tool results to hand back to the provider.

        Returns:
            One provider-native tool-result message per result, in order.
        """
        native: list[Any] = []
        for result in results:
            content = result.error if result.error is not None else self._jsonable(result.result)
            native.append(self._adapter.result_to_native({"call_id": result.call_id, "content": content}))
        return native

    def _parse_arguments(self, arguments: Any) -> Mapping[str, Any]:
        """Return ``arguments`` as a mapping, parsing a JSON string if given.

        Args:
            arguments: Either a JSON object string or a mapping.

        Returns:
            The arguments as a mapping; a JSON string is decoded via
            :func:`json.loads`, a mapping is returned unchanged.
        """
        if isinstance(arguments, str):
            parsed: Any = json.loads(arguments)
            return parsed
        return arguments

    def _jsonable(self, value: Any) -> Any:
        """Coerce ``value`` to a JSON-serialisable form, falling back to str.

        Args:
            value: Any tool result value.

        Returns:
            ``value`` unchanged when it survives a JSON round-trip,
            otherwise its :func:`str` rendering.
        """
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
        return value
