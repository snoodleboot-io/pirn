"""``SpeculativeDraftGenerator`` — a fast, retrieval-free draft answer.

The first stage of Speculative RAG. It answers from the model's parametric
knowledge alone — no retrieval — producing a cheap candidate that a later
verification stage checks against retrieved evidence. Because it does not depend
on the retriever, it runs concurrently with retrieval in the pipeline.

Algorithm:
    1. Validate ``query`` (str) and ``llm`` (:class:`LLMProvider`).
    2. Prompt the LLM for a concise best-effort answer from prior knowledge.
    3. Return the drafted text.

References:
    - Wang et al., "Speculative RAG" (2024): https://arxiv.org/abs/2407.08223
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider


class SpeculativeDraftGenerator(Knot):
    """Produce a fast, retrieval-free draft answer from the query alone."""

    def __init__(
        self,
        *,
        query: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        query: str,
        llm: LLMProvider,
        **_: Any,
    ) -> str:
        """Draft a best-effort answer to ``query`` without retrieval.

        Args:
            query: The user question to draft an answer for.
            llm: The provider generating the draft.

        Returns:
            The drafted answer text.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SpeculativeDraftGenerator: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SpeculativeDraftGenerator: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        prompt = (
            "Give a concise best-effort answer to the question from your own knowledge. "
            "This is a fast draft that will be verified against sources afterwards.\n\n"
            f"Question: {query}\nDraft answer:"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        return self._extract_text(raw)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
