"""``SelfQueryFilterExtractor`` — pull a metadata filter out of a query.

The query-transformation stage of self-query RAG. A natural-language query such
as "recent papers about diffusion models by Ho" carries both a *semantic* part
("diffusion models") and *structured constraints* ("author = Ho"). This knot
asks the LLM to separate the two, returning the cleaned semantic query plus a
metadata filter that the vector store can apply as a pre-filter.

Algorithm:
    1. Validate ``query`` (str), ``llm`` (:class:`LLMProvider`), and
       ``filterable_fields`` (list of str).
    2. Prompt the LLM to emit a JSON object ``{"query": ..., "filter": {...}}``
       using only the whitelisted fields.
    3. Parse the JSON defensively; on any failure, return the original query
       with an empty filter (retrieval degrades to unfiltered, never errors).
    4. Drop filter keys outside ``filterable_fields``.

References:
    - LangChain SelfQueryRetriever design.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class SelfQueryFilterExtractor(Knot):
    """Split a query into a semantic query and a whitelisted metadata filter."""

    def __init__(
        self,
        *,
        query: Knot | str,
        llm: Knot | LLMProvider,
        filterable_fields: Knot | list[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            llm=llm,
            filterable_fields=filterable_fields,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        llm: LLMProvider,
        filterable_fields: list[str],
        **_: Any,
    ) -> Mapping[str, Any]:
        """Return ``{"query": str, "metadata_filter": dict}`` for ``query``.

        Args:
            query: The natural-language query to split.
            llm: The provider that extracts the structured filter.
            filterable_fields: The whitelist of metadata fields the filter may use.

        Returns:
            A mapping with the cleaned semantic ``query`` and a ``metadata_filter``
            restricted to ``filterable_fields``.

        Raises:
            TypeError: If ``query`` is not a string or ``llm`` is not an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SelfQueryFilterExtractor: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SelfQueryFilterExtractor: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        fields = ", ".join(filterable_fields) if filterable_fields else "(none)"
        prompt = (
            "Split the query into a semantic search string and structured metadata "
            "filters. Only use these filter fields: "
            f"{fields}. Respond with a JSON object of the form "
            '{"query": "<semantic text>", "filter": {"field": value}}. '
            "Use an empty filter object when no structured constraint applies.\n\n"
            f"Query: {query}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        semantic_query, metadata_filter = self._parse(self._extract_text(raw), query)
        allowed = set(filterable_fields)
        clean_filter = {k: v for k, v in metadata_filter.items() if k in allowed}
        return {"query": semantic_query, "metadata_filter": clean_filter}

    @staticmethod
    def _parse(text: str, fallback_query: str) -> tuple[str, dict[str, Any]]:
        """Parse the LLM JSON reply, degrading to the original query on failure."""
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return fallback_query, {}
        if not isinstance(parsed, dict):
            return fallback_query, {}
        semantic = parsed.get("query")
        semantic_query = semantic if isinstance(semantic, str) and semantic else fallback_query
        raw_filter = parsed.get("filter")
        metadata_filter = dict(raw_filter) if isinstance(raw_filter, dict) else {}
        return semantic_query, metadata_filter

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
