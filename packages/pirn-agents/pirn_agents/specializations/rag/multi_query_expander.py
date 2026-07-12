"""``MultiQueryExpander`` — reformulate a query into N search variants.

The first stage of RAG-Fusion: ask the LLM to rewrite the user query into
several alternative phrasings that surface different but relevant documents.
The original query is always kept as the first variant so fusion never loses
the literal intent.

Algorithm:
    1. Validate ``query`` (str), ``llm`` (:class:`LLMProvider`), and
       ``num_queries`` (positive int).
    2. Prompt the LLM to produce ``num_queries - 1`` reformulations, one per
       line, with no numbering.
    3. Parse non-empty lines, prepend the original query, de-duplicate while
       preserving order, and cap the list at ``num_queries``.
    4. Fall back to ``[query]`` when parsing yields nothing.

References:
    - Rackauckas, "RAG-Fusion: The Next Frontier of Search Technology" (2024):
      https://arxiv.org/abs/2402.03367
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class MultiQueryExpander(Knot):
    """Expand a query into up to ``num_queries`` reformulations via the LLM."""

    def __init__(
        self,
        *,
        query: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        num_queries: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            llm=llm,
            num_queries=num_queries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        llm: LLMProvider,
        num_queries: int = 4,
        **_: Any,
    ) -> list[str]:
        """Reformulate ``query`` into up to ``num_queries`` variants.

        Args:
            query: The original user query, always kept as the first variant.
            llm: The provider that generates the reformulations.
            num_queries: The maximum number of variants to return (>= 1).

        Returns:
            An ordered, de-duplicated list of query strings, length <= ``num_queries``.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
            ValueError: If ``num_queries`` is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"MultiQueryExpander: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"MultiQueryExpander: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(num_queries, int) or num_queries <= 0:
            raise ValueError(
                f"MultiQueryExpander: num_queries must be a positive int, got {num_queries!r}"
            )
        variants: list[str] = [query]
        if num_queries > 1:
            prompt = (
                f"Rewrite the following search query into {num_queries - 1} alternative "
                "phrasings that would retrieve relevant but differently-worded documents. "
                "Return one phrasing per line with no numbering or commentary.\n\n"
                f"Query: {query}"
            )
            raw = await llm.chat([{"role": "user", "content": prompt}])
            for line in self._extract_text(raw).splitlines():
                stripped = line.strip()
                if stripped and stripped not in variants:
                    variants.append(stripped)
                if len(variants) >= num_queries:
                    break
        return variants[:num_queries]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
