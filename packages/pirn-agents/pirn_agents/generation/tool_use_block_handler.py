"""``ToolUseBlockHandler`` — handle ``{"type": "tool_use", ...}`` blocks.

Contributes a :class:`ToolCall` built from the block's id/name/input fields,
tolerating both the Anthropic (``id``/``input``) and OpenAI-style
(``call_id``/``arguments``) key names. A ``tool_use`` block whose arguments are
not a mapping is left unrecognised (``None``), matching the original parser.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.generation.block_contribution import BlockContribution
from pirn_agents.generation.content_block_handler import ContentBlockHandler
from pirn_agents.tools.tool_call import ToolCall


class ToolUseBlockHandler(ContentBlockHandler):
    """Contribute a :class:`ToolCall` from a ``tool_use`` content block."""

    def try_handle(self, block: Mapping[str, Any]) -> BlockContribution | None:
        """Return the tool-call contribution when ``block`` is a tool-use block."""
        if block.get("type") != "tool_use":
            return None
        arguments = block.get("input") or block.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            return None
        call_id = block.get("id") or block.get("call_id") or ""
        tool_name = block.get("name") or ""
        return BlockContribution(
            tool_call=ToolCall(
                tool_name=str(tool_name),
                arguments=dict(arguments),
                call_id=str(call_id),
            )
        )
