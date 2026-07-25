"""``SubQuestionRetriever`` — concurrent per-sub-question retrieval + union.

The retrieval stage of sub-question RAG. Each sub-question is searched against
the :class:`MemoryStore` **concurrently** (bounded by a concurrency budget) and
the hits are unioned into a single deduplicated context set, preserving the
order in which documents were first seen. Each surviving document records which
``sub_question`` first retrieved it.

Algorithm:
    1. Validate ``sub_questions`` (list), ``store`` (:class:`MemoryStore`),
       ``top_k`` and ``max_concurrency`` (positive ints).
    2. Search every sub-question through an :class:`asyncio.Semaphore` of size
       ``max_concurrency`` and await them together.
    3. Union the hits, keying by ``id`` (or a stable fallback) so a document
       retrieved by several sub-questions appears once.
    4. Return the deduplicated document list in first-seen order.

References:
    - Sub-question query engine pattern (LlamaIndex).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_store import MemoryStore


class SubQuestionRetriever(Knot):
    """Retrieve per sub-question concurrently and union the deduplicated hits."""

    def __init__(
        self,
        *,
        sub_questions: Knot | list[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        top_k: Knot | int = 3,
        max_concurrency: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sub_questions=sub_questions,
            store=store,
            top_k=top_k,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        sub_questions: list[str],
        store: MemoryStore,
        top_k: int = 3,
        max_concurrency: int = 4,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve for each sub-question concurrently and union the hits.

        Args:
            sub_questions: The sub-questions to search for.
            store: The memory store searched once per sub-question.
            top_k: Number of hits fetched per sub-question.
            max_concurrency: Maximum number of in-flight searches.

        Returns:
            The deduplicated union of retrieved documents in first-seen order.

        Raises:
            TypeError: If ``store`` is not a MemoryStore or ``sub_questions`` not a list.
            ValueError: If ``top_k``/``max_concurrency`` are not positive ints.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"SubQuestionRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(sub_questions, list):
            raise TypeError(
                "SubQuestionRetriever: sub_questions must be a list, "
                f"got {type(sub_questions).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"SubQuestionRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(max_concurrency, int) or max_concurrency <= 0:
            raise ValueError(
                "SubQuestionRetriever: max_concurrency must be a positive int, "
                f"got {max_concurrency!r}"
            )
        if not sub_questions:
            return []
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _bounded(sub_question: str) -> tuple[str, list[Mapping[str, Any]]]:
            async with semaphore:
                return sub_question, await self._search(store, sub_question, top_k)

        results = await asyncio.gather(*(_bounded(sub_q) for sub_q in sub_questions))
        merged: dict[str, Mapping[str, Any]] = {}
        for sub_question, hits in results:
            for hit in hits:
                key = self._doc_key(hit)
                if key not in merged:
                    enriched = dict(hit)
                    enriched.setdefault("sub_question", sub_question)
                    merged[key] = enriched
        return list(merged.values())

    @staticmethod
    async def _search(store: MemoryStore, query: str, top_k: int) -> list[Mapping[str, Any]]:
        """Drain ``store.search`` (awaitable / async-iterable / list) into a list."""
        candidate = store.search(query, top_k=top_k)
        if hasattr(candidate, "__await__"):
            candidate = await candidate  # type: ignore[assignment]
        if hasattr(candidate, "__aiter__"):
            collected: list[Mapping[str, Any]] = []
            async for item in candidate:  # type: ignore[misc]
                collected.append(item)
                if len(collected) >= top_k:
                    break
            return collected
        if isinstance(candidate, list):
            return list(candidate[:top_k])
        return [item for item in candidate][:top_k]  # type: ignore[misc]

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))
