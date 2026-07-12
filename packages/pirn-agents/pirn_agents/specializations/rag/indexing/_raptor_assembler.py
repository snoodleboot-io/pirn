"""``_RaptorAssembler`` — build the RAPTOR summary tree from leaf chunks.

Internal terminal knot of :class:`RaptorTreeBuilder`. It recursively clusters
nodes and summarizes each cluster with the LLM, embedding and upserting every
node (leaf + summary) into the vector store, and returns a :class:`RaptorTree`
handle. The tree is content-addressed by a hash of the leaf corpus: a re-ingest
of identical content finds the stored ``:meta`` marker and returns immediately
with ``reused=True``, issuing no LLM summary calls.

Algorithm:
    1. Hash the leaf corpus; if a ``:meta`` marker already exists, return the
       stored tree (reused, no LLM calls).
    2. Level 0: embed the leaf chunks, one node each.
    3. While more than one node remains and the level budget is not spent:
       cluster consecutive nodes into groups of ``cluster_size``, summarize each
       group with the LLM, embed the summaries, and make them the next level.
    4. Upsert all nodes plus a ``:meta`` marker (holding counts, excluded from
       retrieval) and return the :class:`RaptorTree`.

Internal API.
References:
    - Sarthi et al., "RAPTOR" (ICLR 2024): https://arxiv.org/abs/2401.18059
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class _RaptorAssembler(Knot):
    """Recursively cluster + summarize leaves into a stored RAPTOR tree."""

    def __init__(
        self,
        *,
        chunks: Knot | list[str],
        llm: Knot | LLMProvider,
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        _config: KnotConfig,
        cluster_size: Knot | int = 2,
        max_levels: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            llm=llm,
            embedder=embedder,
            store=store,
            cluster_size=cluster_size,
            max_levels=max_levels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: list[str],
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        store: VectorMemoryStore,
        cluster_size: int = 2,
        max_levels: int = 3,
        **_: Any,
    ) -> RaptorTree:
        """Build (or reuse) the RAPTOR tree and return its handle.

        Args:
            chunks: The leaf chunk texts.
            llm: The provider summarizing each cluster.
            embedder: The provider embedding nodes.
            store: The vector store receiving the tree nodes.
            cluster_size: Number of consecutive nodes per cluster.
            max_levels: Maximum number of summary levels above the leaves.

        Returns:
            A :class:`RaptorTree` describing the stored tree.

        Raises:
            TypeError: If ``llm``/``embedder``/``store`` are the wrong type.
            ValueError: If ``cluster_size``/``max_levels`` are not positive ints.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"_RaptorAssembler: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"_RaptorAssembler: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"_RaptorAssembler: store must be a VectorMemoryStore, got {type(store).__name__}"
            )
        if not isinstance(cluster_size, int) or cluster_size <= 1:
            raise ValueError(
                f"_RaptorAssembler: cluster_size must be an int > 1, got {cluster_size!r}"
            )
        if not isinstance(max_levels, int) or max_levels <= 0:
            raise ValueError(
                f"_RaptorAssembler: max_levels must be a positive int, got {max_levels!r}"
            )
        content_hash = hashlib.sha256("\n".join(chunks).encode("utf-8")).hexdigest()[:16]
        prefix = f"raptor:{content_hash}"
        existing = await store.get(f"{prefix}:meta")
        if existing is not None:
            node_count = existing.metadata.get("node_count")
            level_count = existing.metadata.get("level_count")
            return RaptorTree(
                content_hash=content_hash,
                node_count=node_count if isinstance(node_count, int) else 0,
                level_count=level_count if isinstance(level_count, int) else 0,
                reused=True,
            )
        if not chunks:
            return RaptorTree(content_hash=content_hash, node_count=0, level_count=0, reused=False)
        records: list[VectorRecord] = []
        leaf_vectors = await embedder.embed(list(chunks))
        current: list[RaptorNode] = []
        for index, chunk in enumerate(chunks):
            node = RaptorNode.create(
                id=f"{prefix}:0:{index}", level=0, text=chunk, vector=leaf_vectors[index]
            )
            current.append(node)
            records.append(self._record(node))
        node_count = len(current)
        level = 0
        while len(current) > 1 and level < max_levels:
            level += 1
            summaries: list[str] = []
            ids: list[str] = []
            for group_index in range(0, len(current), cluster_size):
                cluster = current[group_index : group_index + cluster_size]
                summaries.append(await self._summarize(llm, [n.text for n in cluster]))
                ids.append(f"{prefix}:{level}:{group_index // cluster_size}")
            summary_vectors = await embedder.embed(summaries)
            next_level: list[RaptorNode] = []
            for position, node_id in enumerate(ids):
                node = RaptorNode.create(
                    id=node_id,
                    level=level,
                    text=summaries[position],
                    vector=summary_vectors[position],
                )
                next_level.append(node)
                records.append(self._record(node))
            current = next_level
            node_count += len(current)
        level_count = level + 1
        records.append(
            VectorRecord.create(
                id=f"{prefix}:meta",
                vector=leaf_vectors[0],
                metadata={
                    "kind": "raptor_meta",
                    "node_count": node_count,
                    "level_count": level_count,
                },
                document=None,
            )
        )
        await store.upsert(records)
        return RaptorTree(
            content_hash=content_hash,
            node_count=node_count,
            level_count=level_count,
            reused=False,
            root=current[0] if current else None,
        )

    @staticmethod
    def _record(node: RaptorNode) -> VectorRecord:
        """Build the vector-store record for a tree node."""
        return VectorRecord.create(
            id=node.id,
            vector=node.vector,
            metadata={"level": node.level, "kind": "raptor"},
            document=node.text,
        )

    @staticmethod
    async def _summarize(llm: LLMProvider, texts: list[str]) -> str:
        """Summarize a cluster of node texts into one concise summary."""
        joined = "\n\n".join(texts)
        prompt = (
            "Summarize the following passages into one concise summary that preserves the "
            f"key facts.\n\n{joined}\n\nSummary:"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
