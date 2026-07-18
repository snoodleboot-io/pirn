"""``NodeEmbeddingIndex`` — the neutral surface the hybrid retriever's vector arm needs.

The graph+vector hybrid retriever's vector arm depends only on this
provider-neutral base: given a query string, return graph node ids ranked by
embedding similarity. The concrete
:class:`~pirn_agents.graph_rag.graph_embedding_index.GraphEmbeddingIndex`
implements it over the F4 embedding + vector-store stack, and mirrored tests can
inject a lightweight stub, so the retriever's fusion logic is exercised without a
real embedder.

The base raises :class:`NotImplementedError` for :meth:`ranked_node_ids` (the
house interface style — never :class:`typing.Protocol`) and is opaque
(:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`) because a concrete index
composes live state (an embedding provider + a vector store): it drops into the
pirn graph as a config value by ``isinstance`` — the very check the retriever
uses to validate an injected index — without descending into the
content-addressed hash. Mirrors the sibling ``store: Knot | GraphStore`` field.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class NodeEmbeddingIndex(PirnOpaqueValue):
    """Abstract vector-arm surface: rank graph node ids by query similarity."""

    async def ranked_node_ids(self, query_text: str, *, top_k: int) -> list[str]:
        """Return up to ``top_k`` node ids ranked by similarity to ``query_text``."""
        raise NotImplementedError(f"{type(self).__name__} must implement ranked_node_ids()")
