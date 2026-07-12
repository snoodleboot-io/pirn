"""``SubQuestionDecomposer`` — split a compound query into sub-questions.

The first stage of sub-question RAG. A complex question ("Compare X and Y on
cost and safety") is broken into independent, self-contained sub-questions that
can each be retrieved for separately, then recombined at synthesis time.

Algorithm:
    1. Validate ``query`` (str), ``llm`` (:class:`LLMProvider`), and
       ``max_sub_questions`` (positive int).
    2. Prompt the LLM to emit at most ``max_sub_questions`` sub-questions, one
       per line, with no numbering.
    3. Parse non-empty lines and cap the list at ``max_sub_questions``.
    4. Fall back to ``[query]`` when parsing yields nothing.

References:
    - Khattab et al., "Demonstrate-Search-Predict" (2022):
      https://arxiv.org/abs/2212.14024
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class SubQuestionDecomposer(Knot):
    """Decompose a compound query into a list of retrievable sub-questions."""

    def __init__(
        self,
        *,
        query: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_sub_questions: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            llm=llm,
            max_sub_questions=max_sub_questions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        llm: LLMProvider,
        max_sub_questions: int = 4,
        **_: Any,
    ) -> list[str]:
        """Decompose ``query`` into at most ``max_sub_questions`` sub-questions.

        Args:
            query: The compound user query to decompose.
            llm: The provider that produces the sub-questions.
            max_sub_questions: Upper bound on the number of sub-questions (>= 1).

        Returns:
            A list of sub-question strings; ``[query]`` when decomposition is empty.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
            ValueError: If ``max_sub_questions`` is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SubQuestionDecomposer: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SubQuestionDecomposer: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_sub_questions, int) or max_sub_questions <= 0:
            raise ValueError(
                "SubQuestionDecomposer: max_sub_questions must be a positive int, "
                f"got {max_sub_questions!r}"
            )
        prompt = (
            f"Break the following question into at most {max_sub_questions} independent, "
            "self-contained sub-questions that together cover it. Return one sub-question "
            "per line with no numbering or commentary.\n\n"
            f"Question: {query}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        sub_questions = [
            line.strip() for line in self._extract_text(raw).splitlines() if line.strip()
        ]
        capped = sub_questions[:max_sub_questions]
        return capped if capped else [query]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
