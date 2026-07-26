"""Unit tests for :class:`PairwisePromptBuilder` (S3)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.pairwise_prompt_builder import PairwisePromptBuilder


class PairwisePromptBuilderTests(unittest.TestCase):
    def test_builds_single_user_message(self) -> None:
        # Arrange
        builder = PairwisePromptBuilder()

        # Act
        messages = builder.build(prompt="q", first_text="x", second_text="y")

        # Assert
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_first_text_is_response_a_second_is_response_b(self) -> None:
        # Arrange
        builder = PairwisePromptBuilder()

        # Act
        content = builder.build(prompt="the-prompt", first_text="alpha", second_text="beta")[0][
            "content"
        ]

        # Assert
        assert "Prompt: the-prompt" in content
        assert "Response A: alpha" in content
        assert "Response B: beta" in content
        assert "'A', 'B', or 'tie'" in content

    def test_presentation_order_is_positional(self) -> None:
        # Arrange
        builder = PairwisePromptBuilder()

        # Act: swap the two texts into the opposite slots
        content = builder.build(prompt="q", first_text="beta", second_text="alpha")[0]["content"]

        # Assert
        assert "Response A: beta" in content
        assert "Response B: alpha" in content


if __name__ == "__main__":
    unittest.main()
