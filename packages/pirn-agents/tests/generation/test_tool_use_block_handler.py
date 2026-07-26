"""Unit tests for :class:`ToolUseBlockHandler`."""

from __future__ import annotations

import unittest

from pirn_agents.generation.tool_use_block_handler import ToolUseBlockHandler


class TestToolUseBlockHandler(unittest.TestCase):
    def test_handles_anthropic_style_tool_use(self) -> None:
        contribution = ToolUseBlockHandler().try_handle(
            {"type": "tool_use", "id": "call-1", "name": "search", "input": {"q": "x"}}
        )

        assert contribution is not None
        assert contribution.tool_call is not None
        assert contribution.tool_call.tool_name == "search"
        assert contribution.tool_call.call_id == "call-1"
        assert contribution.tool_call.arguments == {"q": "x"}
        assert contribution.text is None

    def test_handles_openai_style_keys(self) -> None:
        contribution = ToolUseBlockHandler().try_handle(
            {"type": "tool_use", "call_id": "c9", "name": "lookup", "arguments": {"k": 1}}
        )

        assert contribution is not None
        assert contribution.tool_call is not None
        assert contribution.tool_call.call_id == "c9"
        assert contribution.tool_call.arguments == {"k": 1}

    def test_ignores_non_tool_use_block(self) -> None:
        assert ToolUseBlockHandler().try_handle({"type": "text", "text": "x"}) is None

    def test_ignores_tool_use_with_non_mapping_arguments(self) -> None:
        assert (
            ToolUseBlockHandler().try_handle(
                {"type": "tool_use", "name": "search", "input": "not-a-mapping"}
            )
            is None
        )


if __name__ == "__main__":
    unittest.main()
