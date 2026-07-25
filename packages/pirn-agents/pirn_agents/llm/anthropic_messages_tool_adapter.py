"""``AnthropicMessagesToolAdapter`` — tool-calling shaping for the Messages API wire format.

The Messages API is a deliberately *distinct* wire shape from chat-completions:
tool calls arrive as ``tool_use`` content blocks (with the arguments already a
JSON object, not a string), and results are returned as ``tool_result`` blocks
inside a user message. This adapter is an equal peer of
:class:`pirn_agents.llm.openai_compatible_tool_adapter.OpenAICompatibleToolAdapter`.

Native shapes handled:

* declaration — ``{"name", "description", "input_schema"}``
* assistant tool calls — ``content[*]`` blocks of type ``tool_use`` with
  ``{"id", "name", "input": <object>}``
* tool result — a user message carrying a ``tool_result`` block
"""

from __future__ import annotations

from typing import Any

from pirn_agents.provider_adapter import ProviderAdapter


class AnthropicMessagesToolAdapter(ProviderAdapter):
    """Neutral ↔ Messages-API ``tool_use``/``tool_result`` translation."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        """Shape one neutral tool into an ``input_schema`` declaration."""
        return {
            "name": neutral_tool["name"],
            "description": neutral_tool["description"],
            "input_schema": neutral_tool["parameters"],
        }

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        """Pull neutral tool-call dicts from ``tool_use`` content blocks.

        ``provider_msg`` is the full response object; its ``content`` list is
        scanned for ``tool_use`` blocks. ``arguments`` is the block's ``input``
        object (already a mapping).
        """
        calls: list[dict[str, Any]] = []
        for block in provider_msg.get("content") or []:
            if block.get("type") == "tool_use":
                calls.append(
                    {
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {}),
                    }
                )
        return calls

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        """Shape a neutral tool result into a user ``tool_result`` message."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": result_payload["call_id"],
                    "content": result_payload["content"],
                }
            ],
        }
