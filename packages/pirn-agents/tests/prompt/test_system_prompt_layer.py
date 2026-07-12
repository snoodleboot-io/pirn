"""Unit tests for :class:`SystemPromptLayer`."""

from __future__ import annotations

import unittest

from pirn_agents.prompt.system_prompt_layer import SystemPromptLayer


class TestValidation(unittest.TestCase):
    def test_rejects_empty_kind(self) -> None:
        with self.assertRaisesRegex(TypeError, "kind"):
            SystemPromptLayer(kind="", content="x")

    def test_rejects_non_str_content(self) -> None:
        with self.assertRaisesRegex(TypeError, "content"):
            SystemPromptLayer(kind="persona", content=1)  # type: ignore[arg-type]

    def test_rejects_non_str_title(self) -> None:
        with self.assertRaisesRegex(TypeError, "title"):
            SystemPromptLayer(kind="persona", content="x", title=2)  # type: ignore[arg-type]


class TestIsEmpty(unittest.TestCase):
    def test_blank_content_is_empty(self) -> None:
        assert SystemPromptLayer(kind="persona", content="   \n").is_empty()

    def test_non_blank_content_is_not_empty(self) -> None:
        assert not SystemPromptLayer(kind="persona", content="hi").is_empty()


if __name__ == "__main__":
    unittest.main()
