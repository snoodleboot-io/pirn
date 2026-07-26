"""Unit tests for :class:`RubricPromptBuilder` (S3)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.rubric_criterion import RubricCriterion
from pirn_agents.evaluation.rubric_prompt_builder import RubricPromptBuilder


class RubricPromptBuilderTests(unittest.TestCase):
    def test_builds_single_user_message(self) -> None:
        # Arrange
        builder = RubricPromptBuilder()
        criterion = RubricCriterion(name="correctness", description="is it right")

        # Act
        messages = builder.build(prompt="q", response="r", criterion=criterion)

        # Assert
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_content_embeds_criterion_prompt_and_response(self) -> None:
        # Arrange
        builder = RubricPromptBuilder()
        criterion = RubricCriterion(name="correctness", description="is it right")

        # Act
        content = builder.build(prompt="the-prompt", response="the-response", criterion=criterion)[
            0
        ]["content"]

        # Assert
        assert "Criterion: correctness — is it right" in content
        assert "Prompt: the-prompt" in content
        assert "Response: the-response" in content
        assert "0.0-1.0" in content

    def test_empty_description_still_renders(self) -> None:
        # Arrange
        builder = RubricPromptBuilder()
        criterion = RubricCriterion(name="style")

        # Act
        content = builder.build(prompt="q", response="r", criterion=criterion)[0]["content"]

        # Assert
        assert "Criterion: style — \n" in content


if __name__ == "__main__":
    unittest.main()
