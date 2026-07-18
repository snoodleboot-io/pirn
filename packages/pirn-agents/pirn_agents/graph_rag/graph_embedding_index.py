"""``GraphEmbeddingIndex`` — node/edge embeddings over the F4 vector stack.

Generates embeddings for graph elements provider-neutrally through the existing
F4 :class:`~pirn.core.providers.embedding_provider.EmbeddingProvider` and stores
the resulting vectors alongside the graph in a
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore` (the
zero-dep :class:`InMemoryVectorStore` by default). Nodes and edges are tagged
with a ``kind`` metadata flag so the vector arm of hybrid retrieval can rank
*nodes* by similarity to a query while keeping edge vectors out of the node
ranking. Subclasses the
:class:`~pirn_agents.graph_rag.node_embedding_index.NodeEmbeddingIndex` base.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.graph_rag.node_embedding_index import NodeEmbeddingIndex
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class GraphEmbeddingIndex(NodeEmbeddingIndex):
    """Embed graph nodes/edges via F4 and rank nodes by query similarity."""

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        store: VectorMemoryStore | None = None,
    ) -> None:
        """Initialise the index over an embedding provider and a vector store.

        Args:
            embedder: The F4 embedding provider used to embed graph elements and
                queries. Must be an :class:`EmbeddingProvider`.
            store: Optional backing vector store; defaults to a zero-dependency
                :class:`InMemoryVectorStore`.

        Raises:
            TypeError: If ``embedder`` is not an :class:`EmbeddingProvider` or
                ``store`` is not a :class:`VectorMemoryStore`.
        """
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"GraphEmbeddingIndex: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if store is not None and not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"GraphEmbeddingIndex: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        self._embedder: EmbeddingProvider = embedder
        self._store: VectorMemoryStore = store if store is not None else InMemoryVectorStore()
        self._node_count: int = 0

    async def index_nodes(self, nodes: Sequence[GraphNode]) -> None:
        """Embed ``nodes`` and upsert their vectors (tagged ``kind="node"``)."""
        items = list(nodes)
        if not items:
            return
        vectors = await self._embedder.embed([self._node_text(node) for node in items])
        records = [
            VectorRecord.create(
                id=node.id,
                vector=vector,
                metadata={"kind": "node", "type": node.type},
                document=self._node_text(node),
            )
            for node, vector in zip(items, vectors, strict=True)
        ]
        await self._store.upsert(records)
        self._node_count += len(records)

    async def index_edges(self, edges: Sequence[GraphEdge]) -> None:
        """Embed ``edges`` and upsert their vectors (tagged ``kind="edge"``)."""
        items = list(edges)
        if not items:
            return
        vectors = await self._embedder.embed([self._edge_text(edge) for edge in items])
        records = [
            VectorRecord.create(
                id=edge.id,
                vector=vector,
                metadata={"kind": "edge", "type": edge.type},
                document=self._edge_text(edge),
            )
            for edge, vector in zip(items, vectors, strict=True)
        ]
        await self._store.upsert(records)

    async def ranked_node_ids(self, query_text: str, *, top_k: int) -> list[str]:
        """Return up to ``top_k`` node ids ranked by similarity to ``query_text``.

        Args:
            query_text: The text query to embed and match against node vectors.
            top_k: Maximum number of node ids to return. Must be positive.

        Returns:
            Node ids ordered by descending similarity (edge vectors excluded).

        Raises:
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"GraphEmbeddingIndex: top_k must be a positive int, got {top_k!r}")
        vectors = await self._embedder.embed([query_text])
        matches = await self._store.query(vectors[0], top_k=top_k, metadata_filter={"kind": "node"})
        return [match.id for match in matches]

    def is_empty(self) -> bool:
        """Return whether any nodes have been indexed yet."""
        return self._node_count == 0

    async def close(self) -> None:
        """Release the backing vector store."""
        await self._store.close()

    @staticmethod
    def _node_text(node: GraphNode) -> str:
        """Render a node into the text embedded for similarity search."""
        parts: list[str] = [node.type]
        for key in sorted(node.properties):
            parts.append(str(node.properties[key]))
        return " ".join(parts)

    @staticmethod
    def _edge_text(edge: GraphEdge) -> str:
        """Render an edge into the text embedded for similarity search."""
        return f"{edge.source_id} {edge.type} {edge.target_id}"
