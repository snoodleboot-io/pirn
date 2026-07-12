"""``IterativeRetriever`` — bounded recursive retrieve-and-refine loop.

Iterative (a.k.a. recursive) retrieval retrieves, inspects what came back, and —
if the evidence looks incomplete — asks the LLM for a sharper follow-up query
and retrieves again. The loop is hard-bounded by ``max_iterations`` so it always
terminates, and accumulated hits are deduplicated across rounds.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), ``max_iterations`` and ``top_k`` (positive ints).
    2. Start with ``current_query = query``. Repeat up to ``max_iterations``:
       a. Search ``memory`` for ``top_k`` hits; union them (dedup by id).
       b. On the final allowed iteration, stop.
       c. Otherwise ask the LLM to reply ``DONE`` (evidence sufficient) or
          ``REFINE: <follow-up query>``; on ``REFINE`` set ``current_query`` and
          loop, on anything else stop.
    3. Return the accumulated deduplicated documents.

References:
    - Asai et al., "Self-RAG" (2023): https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.memory_store import MemoryStore


class IterativeRetriever(Knot):
    """Retrieve, ask the LLM whether to refine, and loop under a budget."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_iterations: Knot | int = 3,
        top_k: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            max_iterations=max_iterations,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        max_iterations: int = 3,
        top_k: int = 3,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Run the bounded retrieve-and-refine loop and return the union of hits.

        Args:
            query: The initial query.
            memory: The memory store searched each round.
            llm: The provider deciding whether to refine.
            max_iterations: Hard upper bound on retrieval rounds (>= 1).
            top_k: Hits fetched per round.

        Returns:
            The deduplicated union of documents retrieved across rounds.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
            ValueError: If ``max_iterations``/``top_k`` are not positive ints.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"IterativeRetriever: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"IterativeRetriever: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"IterativeRetriever: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"IterativeRetriever: max_iterations must be a positive int, got {max_iterations!r}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"IterativeRetriever: top_k must be a positive int, got {top_k!r}")
        merged: dict[str, Mapping[str, Any]] = {}
        current_query = query
        for iteration in range(max_iterations):
            hits = await self._search(memory, current_query, top_k)
            for hit in hits:
                key = self._doc_key(hit)
                if key not in merged:
                    enriched = dict(hit)
                    enriched.setdefault("iteration", iteration)
                    merged[key] = enriched
            if iteration == max_iterations - 1:
                break
            follow_up = await self._decide(llm, query, merged, current_query)
            if follow_up is None:
                break
            current_query = follow_up
        return list(merged.values())

    @staticmethod
    async def _decide(
        llm: LLMProvider,
        original_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        current_query: str,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop."""
        context = "\n".join(str(doc) for doc in merged.values()) or "(nothing yet)"
        prompt = (
            "You are running iterative retrieval. Given the original question and the "
            "evidence gathered so far, reply with exactly 'DONE' if the evidence is "
            "sufficient, or 'REFINE: <a sharper follow-up search query>' if more is "
            f"needed.\n\nOriginal question: {original_query}\n"
            f"Last query: {current_query}\n\nEvidence:\n{context}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = IterativeRetriever._extract_text(raw).strip()
        if reply.upper().startswith("REFINE:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None

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

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
