"""Interface every provider-specific tool-calling adapter must satisfy.

The provider-neutral :class:`pirn_agents.tool_call_codec.ToolCallCodec`
delegates all provider-specific shaping to a :class:`ProviderAdapter`.
Concrete adapters translate between pirn's neutral vocabulary and one
LLM provider's native tool-calling JSON in three places:

* declaring tools to the provider (:meth:`tool_to_native`),
* reading tool calls out of a provider's assistant message
  (:meth:`extract_tool_calls`),
* handing tool results back to the provider (:meth:`result_to_native`).

Keeping every provider assumption behind this interface is what lets the
codec stay free of provider-specific logic. Adapters are opaque to
pydantic (see :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the
default identity serialiser keeps content-addressing stable.
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ProviderAdapter(PirnOpaqueValue):
    """Interface translating neutral tool-calling shapes to one provider."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        """Shape one neutral tool dict into this provider's native form.

        Args:
            neutral_tool: A ``{"name", "description", "parameters"}`` entry
                as produced by :meth:`pirn_agents.toolset.Toolset.schema`.

        Returns:
            The provider-native tool / function-declaration JSON.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement tool_to_native()")

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        """Pull raw tool-call dicts out of a provider assistant message.

        Args:
            provider_msg: A provider-native assistant message that may carry
                one or more tool calls.

        Returns:
            One dict per tool call, each with an ``id``, a ``name``, and
            ``arguments`` as either a JSON string or a mapping.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement extract_tool_calls()")

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        """Shape one neutral tool-result payload into the provider's form.

        Args:
            result_payload: A neutral ``{"call_id", "content"}`` payload.

        Returns:
            The provider-native tool-result message.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement result_to_native()")
