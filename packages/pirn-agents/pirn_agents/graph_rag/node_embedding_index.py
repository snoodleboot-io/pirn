"""``NodeEmbeddingIndex`` — the neutral surface the hybrid retriever's vector arm needs.

The graph+vector hybrid retriever's vector arm depends only on this
provider-neutral protocol: given a query string, return graph node ids ranked by
embedding similarity. The concrete
:class:`~pirn_agents.graph_rag.graph_embedding_index.GraphEmbeddingIndex`
implements it over the F4 embedding + vector-store stack, and mirrored tests can
inject a lightweight stub, so the retriever's fusion logic is exercised without a
real embedder.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NodeEmbeddingIndex(Protocol):
    """Neutral vector-arm surface: rank graph node ids by query similarity."""

    async def ranked_node_ids(self, query_text: str, *, top_k: int) -> list[str]:
        """Return up to ``top_k`` node ids ranked by similarity to ``query_text``."""
        ...
