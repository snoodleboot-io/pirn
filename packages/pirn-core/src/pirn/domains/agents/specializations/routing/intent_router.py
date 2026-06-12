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
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class IntentRouter(Knot):
    """LLM-based intent classifier; returns a category label string."""

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
            TypeError: If message is not a string or llm is not an LLMProvider.
            ValueError: If categories is empty or contains invalid entries.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"IntentRouter: llm must be an LLMProvider, got {type(llm).__name__}")
        categories_tuple = tuple(categories)
        if not categories_tuple:
            raise ValueError("IntentRouter: categories must be a non-empty sequence")
        for index, cat in enumerate(categories_tuple):
            if not isinstance(cat, str) or not cat:
                raise ValueError(
                    f"IntentRouter: categories[{index}] must be a non-empty string, got {cat!r}"
                )
        if not isinstance(message, str):
            raise TypeError(f"IntentRouter: message must be a string, got {type(message).__name__}")
        category_list = ", ".join(categories_tuple)
        prompt = (
            f"Classify the following message into exactly one of these "
            f"categories: {category_list}.\n"
            "Reply with the category name only.\n\n"
            f"Message: {message}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        label = self._extract_text(raw).strip()
        if label in categories_tuple:
            return label
        for cat in categories_tuple:
            if cat.lower() in label.lower():
                return cat
        return categories_tuple[0]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
