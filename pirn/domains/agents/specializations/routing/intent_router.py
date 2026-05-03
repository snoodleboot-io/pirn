"""``IntentRouter`` — classify user message intent via LLM.

A :class:`Knot` that sends the user message plus the configured
category list to an LLM and returns the category label string that
best describes the message intent.
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
        llm: LLMProvider,
        categories: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "IntentRouter: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not categories:
            raise ValueError(
                "IntentRouter: categories must be a non-empty sequence"
            )
        for index, cat in enumerate(categories):
            if not isinstance(cat, str) or not cat:
                raise ValueError(
                    f"IntentRouter: categories[{index}] must be a non-empty "
                    f"string, got {cat!r}"
                )
        self._llm = llm
        self._categories = tuple(categories)
        super().__init__(message=message, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        **_: Any,
    ) -> str:
        """Classify the message intent and return the matching category label.

        Args:
            message: The user message to classify.

        Returns:
            The category label string most closely matching the message intent.

        Raises:
            TypeError: If message is not a string.
        """
        if not isinstance(message, str):
            raise TypeError(
                "IntentRouter: message must be a string, "
                f"got {type(message).__name__}"
            )
        category_list = ", ".join(self._categories)
        prompt = (
            f"Classify the following message into exactly one of these "
            f"categories: {category_list}.\n"
            "Reply with the category name only.\n\n"
            f"Message: {message}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        label = self._extract_text(raw).strip()
        if label in self._categories:
            return label
        for cat in self._categories:
            if cat.lower() in label.lower():
                return cat
        return self._categories[0]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
