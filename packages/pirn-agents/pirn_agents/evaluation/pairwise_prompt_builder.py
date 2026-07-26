"""``PairwisePromptBuilder`` — build the judge prompt for one A-vs-B comparison."""

from __future__ import annotations

from typing import Any


class PairwisePromptBuilder:
    """Construct the provider-neutral chat prompt for a pairwise comparison.

    The two texts are supplied in *presentation order* (``first_text`` is shown
    as "Response A"); the caller controls position-swap by choosing which real
    response occupies each slot, so this builder stays presentation-only.
    """

    def build(
        self,
        *,
        prompt: str,
        first_text: str,
        second_text: str,
    ) -> list[dict[str, Any]]:
        """Return the chat messages asking which presented response is better.

        Args:
            prompt: The original prompt both responses answer.
            first_text: The response shown first (as "Response A").
            second_text: The response shown second (as "Response B").

        Returns:
            A single-message chat sequence in role/content form.
        """
        return [
            {
                "role": "user",
                "content": (
                    "Which response better answers the prompt? "
                    "Reply with 'A', 'B', or 'tie'.\n"
                    f"Prompt: {prompt}\n\n"
                    f"Response A: {first_text}\n\nResponse B: {second_text}"
                ),
            }
        ]
