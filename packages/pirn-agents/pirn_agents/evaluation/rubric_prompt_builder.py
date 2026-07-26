"""``RubricPromptBuilder`` — build the judge prompt for one rubric criterion."""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.rubric_criterion import RubricCriterion


class RubricPromptBuilder:
    """Construct the provider-neutral chat prompt for scoring one criterion.

    Keeping prompt construction in a dedicated collaborator lets the judge stay
    a thin orchestrator and lets the exact wording be unit-tested in isolation.
    """

    def build(
        self,
        *,
        prompt: str,
        response: str,
        criterion: RubricCriterion,
    ) -> list[dict[str, Any]]:
        """Return the chat messages asking the judge to score ``response``.

        The judge is asked to reply with a bare ``0.0``-``1.0`` number for the
        given criterion; the caller parses that reply with a score parser.

        Args:
            prompt: The original prompt the response answers.
            response: The response text to score.
            criterion: The weighted rubric dimension being scored.

        Returns:
            A single-message chat sequence in role/content form.
        """
        return [
            {
                "role": "user",
                "content": (
                    "Score the response for the criterion on a 0.0-1.0 scale. "
                    "Reply with just the number.\n"
                    f"Criterion: {criterion.name} — {criterion.description}\n"
                    f"Prompt: {prompt}\n\nResponse: {response}"
                ),
            }
        ]
