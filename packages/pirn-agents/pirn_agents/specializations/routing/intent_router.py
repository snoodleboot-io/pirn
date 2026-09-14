# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``IntentRouter`` — classify user message intent via LLM.

A :class:`Knot` that sends the user message plus the configured
category list to an LLM and returns the category label string that
best describes the message intent.

Algorithm:
    1. Receive the resolved ``message`` string, ``llm`` provider, and
       ``categories`` sequence at process time.
    2. Validate input types; raise on bad types or empty categories.
    3. Render a classification prompt listing all category labels.
    4. Call ``llm.chat`` with the prompt.
    5. Extract the text label from the raw LLM response.
    6. Return the label if it matches a known category exactly.
    7. Fall back to a case-insensitive substring search over known categories.
    8. If no match is found, return the first category in the sequence.


References:
    - pirn-native routing pattern; no external algorithm reference.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.router import Router
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class IntentRouter(Router):
    """LLM-based intent classifier; returns a category label string."""

    _classification_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.routing.intent_router.classification_prompt",
        default=(
            "Classify the following message into exactly one of these "
            "categories: {{ categories }}.\n"
            "Reply with the category name only.\n\n"
            "Message: {{ message }}"
        ),
    )

    def __init__(
        self,
        *,
        message: Knot | str,
        llm: Knot | LLMProvider,
        categories: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, llm=llm, categories=categories, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        llm: LLMProvider,
        categories: Sequence[str],
        **_: Any,
    ) -> str:
        """Classify the message intent and return the matching category label.

        Args:
            message: The user message to classify.
            llm: The LLM provider used to classify the intent.
            categories: A non-empty sequence of category label strings.

        Returns:
            The category label string most closely matching the message intent.

        Raises:
            ValueError: If categories is empty or contains invalid entries.
        """
        categories_tuple = tuple(categories)
        if not categories_tuple:
            raise ValueError("IntentRouter: categories must be a non-empty sequence")
        for index, cat in enumerate(categories_tuple):
            if not isinstance(cat, str) or not cat:
                raise ValueError(
                    f"IntentRouter: categories[{index}] must be a non-empty string, got {cat!r}"
                )
        category_list = ", ".join(categories_tuple)
        prompt = type(self)._classification_prompt.render(
            {"categories": category_list, "message": message},
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        label = LlmResponseText().extract(raw).strip()
        if label in categories_tuple:
            return label
        for cat in categories_tuple:
            if cat.lower() in label.lower():
                return cat
        return categories_tuple[0]
