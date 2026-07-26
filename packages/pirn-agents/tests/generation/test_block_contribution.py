"""Unit tests for :class:`BlockContribution`."""

from __future__ import annotations

import unittest

from pirn_agents.generation.block_contribution import BlockContribution
from pirn_agents.tools.tool_call import ToolCall


class TestBlockContribution(unittest.TestCase):
    def test_defaults_are_none(self) -> None:
        contribution = BlockContribution()

        assert contribution.text is None
        assert contribution.tool_call is None

    def test_carries_text(self) -> None:
        contribution = BlockContribution(text="hello")

        assert contribution.text == "hello"
        assert contribution.tool_call is None

    def test_carries_tool_call(self) -> None:
        call = ToolCall(tool_name="search", arguments={"q": "x"}, call_id="c1")
        contribution = BlockContribution(tool_call=call)

        assert contribution.tool_call is call
        assert contribution.text is None


if __name__ == "__main__":
    unittest.main()
