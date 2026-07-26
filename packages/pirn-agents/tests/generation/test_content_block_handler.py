"""Unit tests for the :class:`ContentBlockHandler` interface base."""

from __future__ import annotations

import unittest

from pirn_agents.generation.content_block_handler import ContentBlockHandler


class TestContentBlockHandlerInterface(unittest.TestCase):
    def test_try_handle_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "try_handle"):
            ContentBlockHandler().try_handle({"type": "text", "text": "x"})


if __name__ == "__main__":
    unittest.main()
