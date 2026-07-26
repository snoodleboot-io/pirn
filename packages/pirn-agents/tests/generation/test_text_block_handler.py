"""Unit tests for :class:`TextBlockHandler`."""

from __future__ import annotations

import unittest

from pirn_agents.generation.text_block_handler import TextBlockHandler


class TestTextBlockHandler(unittest.TestCase):
    def test_handles_text_block(self) -> None:
        contribution = TextBlockHandler().try_handle({"type": "text", "text": "hello"})

        assert contribution is not None
        assert contribution.text == "hello"
        assert contribution.tool_call is None

    def test_ignores_non_text_block(self) -> None:
        assert TextBlockHandler().try_handle({"type": "tool_use"}) is None

    def test_ignores_text_block_with_non_string_text(self) -> None:
        assert TextBlockHandler().try_handle({"type": "text", "text": 123}) is None


if __name__ == "__main__":
    unittest.main()
