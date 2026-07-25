"""``FusionRetriever`` — concurrent multi-query retrieval fused with RRF.

The retrieval stage of RAG-Fusion. Given a list of query variants, it searches
the :class:`MemoryStore` for each variant **concurrently** (bounded by a
concurrency budget), builds one ranked id list per variant, and fuses them with
Reciprocal Rank Fusion. Documents are de-duplicated by identity and returned in
fused-score order, each carrying its ``fusion_score``.

Algorithm:
    1. Validate ``queries`` (list of str), ``store`` (:class:`MemoryStore`),
       ``top_k``, ``max_concurrency``, and ``rrf_k`` (positive ints).
    2. Launch one search per query through an :class:`asyncio.Semaphore` of
       size ``max_concurrency`` and await them together.
    3. Key each hit by its ``id`` (or a stable fallback), record the first-seen
       mapping, and build per-query ranked key lists.
    4. Fuse the ranked lists via
       :func:`~pirn_agents.retrieval.reciprocal_rank_fusion.reciprocal_rank_fusion`.
    5. Return the top ``top_k`` fused documents, each with a ``fusion_score``.

References:
    - Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion" (SIGIR 2009).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_store import MemoryStore
from pirn_agents.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion


class FusionRetriever(Knot):
    """Search each query variant concurrently and fuse the rankings with RRF."""

    def __init__(
        self,
        *,
        queries: Knot | list[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        max_concurrency: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            queries=queries,
            store=store,
            top_k=top_k,
            max_concurrency=max_concurrency,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        queries: list[str],
        store: MemoryStore,
        top_k: int = 5,
        max_concurrency: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve for every query concurrently and fuse the rankings.

        Args:
            queries: The query variants to search for.
            store: The memory store searched once per variant.
            top_k: Number of fused documents to return.
            max_concurrency: Maximum number of in-flight searches.
            rrf_k: The RRF damping constant.

        Returns:
            Up to ``top_k`` document mappings ordered by fused score, each with a
            ``fusion_score`` key.

        Raises:
            TypeError: If ``store`` is not a MemoryStore or ``queries`` is not a list.
            ValueError: If ``top_k``/``max_concurrency``/``rrf_k`` are not positive ints.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"FusionRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(queries, list):
            raise TypeError(
                f"FusionRetriever: queries must be a list, got {type(queries).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"FusionRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(max_concurrency, int) or max_concurrency <= 0:
            raise ValueError(
                f"FusionRetriever: max_concurrency must be a positive int, got {max_concurrency!r}"
            )
        if not isinstance(rrf_k, int) or rrf_k <= 0:
            raise ValueError(f"FusionRetriever: rrf_k must be a positive int, got {rrf_k!r}")
        if not queries:
            return []
        fetch = top_k * 2
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _bounded(query: str) -> list[Mapping[str, Any]]:
            async with semaphore:
                return await self._search(store, query, fetch)

        per_query_hits = await asyncio.gather(*(_bounded(query) for query in queries))
        representative: dict[str, Mapping[str, Any]] = {}
        rankings: list[list[str]] = []
        for hits in per_query_hits:
            ranking: list[str] = []
            for hit in hits:
                key = self._doc_key(hit)
                representative.setdefault(key, hit)
                ranking.append(key)
            rankings.append(ranking)
        fused = reciprocal_rank_fusion(rankings, k=rrf_k)
        results: list[Mapping[str, Any]] = []
        for key, score in fused[:top_k]:
            merged = dict(representative[key])
            merged["fusion_score"] = score
            results.append(merged)
        return results

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
