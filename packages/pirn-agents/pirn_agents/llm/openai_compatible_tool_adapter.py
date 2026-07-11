"""``OpenAICompatibleToolAdapter`` — tool-calling shaping for the chat-completions wire format.

Translates neutral tool shapes to/from the ``chat/completions`` function-calling
JSON that many servers speak (self-hosted engines, gateways, and hosted APIs
alike). This is a *wire-protocol* adapter, not a vendor endorsement; it is a
peer of :class:`pirn_agents.llm.anthropic_messages_tool_adapter.AnthropicMessagesToolAdapter`.

Native shapes handled:

* declaration — ``{"type": "function", "function": {name, description, parameters}}``
* assistant tool calls — ``message.tool_calls[*]`` with
  ``{"id", "function": {"name", "arguments": <json string>}}``
* tool result — a ``{"role": "tool", "tool_call_id", "content"}`` message
"""

from __future__ import annotations

from typing import Any

from pirn_agents.provider_adapter import ProviderAdapter


class OpenAICompatibleToolAdapter(ProviderAdapter):
    """Neutral ↔ chat-completions function-calling translation."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        """Shape one neutral tool into a ``type=function`` declaration."""
        return {
            "type": "function",
            "function": {
                "name": neutral_tool["name"],
                "description": neutral_tool["description"],
                "parameters": neutral_tool["parameters"],
            },
        }

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        """Pull neutral tool-call dicts from an assistant message.

        ``provider_msg`` is the assistant ``message`` object; a missing or
        empty ``tool_calls`` yields an empty list.
        """
        calls: list[dict[str, Any]] = []
        for call in provider_msg.get("tool_calls") or []:
            function = call.get("function") or {}
            calls.append(
                {
                    "id": call.get("id", ""),
                    "name": function.get("name", ""),
                    "arguments": function.get("arguments", "{}"),
                }
            )
        return calls

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        """Shape a neutral tool result into a ``role=tool`` message."""
        return {
            "role": "tool",
            "tool_call_id": result_payload["call_id"],
            "content": result_payload["content"],
        }
