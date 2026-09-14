"""``_LexicalIds`` — rank the BM25 lexical arm's candidate ids on a worker thread.

Internal per-arm knot for
:class:`~pirn_agents.retrieval.hybrid_retriever.HybridRetriever`'s fan-out
(PIR-867). ``Bm25Index`` predates :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`
and has no pydantic-compatible schema, so — mirroring the existing
``lexical: Knot | Any`` field on :class:`~pirn_agents.retrieval.hybrid_retriever_base.HybridRetrieverBase`'s
concretes — it is typed ``Any`` here too and checked with ``isinstance`` in
``process()``. The scoring work is CPU-bound, so it still runs on a worker
thread via ``asyncio.to_thread`` exactly as it did inside the old
``asyncio.gather`` call — ``asyncio.to_thread`` copies the contextvars
context (``run_in_executor`` does not), so the active ``RunNesting`` frame
and ``AgentToolPolicy`` still survive the thread hop.

Internal API.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.bm25_index import Bm25Index


class _LexicalIds(Knot):
    """Search the BM25 index on a worker thread and return the top ``fetch`` ids."""

    def __init__(
        self,
        *,
        lexical: Knot | Any,
        query: Knot | str,
        fetch: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(lexical=lexical, query=query, fetch=fetch, _config=_config, **kwargs)

    async def process(self, lexical: Any, query: str, fetch: int, **_: Any) -> list[str]:
        """Return the BM25-ranked ids for ``query``, most relevant first.

        Raises:
            TypeError: If ``lexical`` is not a :class:`Bm25Index`.
        """
        if not isinstance(lexical, Bm25Index):
            raise TypeError(
                f"_LexicalIds: lexical must be a Bm25Index, got {type(lexical).__name__}"
            )
        return await asyncio.to_thread(_LexicalIds._search, lexical, query, fetch)

    @staticmethod
    def _search(lexical: Bm25Index, query: str, fetch: int) -> list[str]:
        return [doc_id for doc_id, _ in lexical.search(query, top_k=fetch)]
