"""``RaptorAssembler`` — build the RAPTOR summary tree from leaf chunks.

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

Extends :class:`~pirn.core.assembler.Assembler` for the family-membership
signal (this is the terminal node that assembles the final
:class:`RaptorTree` for :class:`RaptorTreeBuilder`), not the strict "raw
bytes in, no I/O" Assembler contract: this knot performs an atomic
read-check-transform-write cycle against the vector store (dedup lookup,
LLM summarization, embedding, upsert) the same way ``ScdType2``,
``MergeUpsert`` and ``CDCDebezium`` do — the ETL exception documented in
``docs/contributing/assembler-disassembler-pattern.md`` ("Not required for
ETL knots that perform an atomic read-transform-write cycle against a pool
or broker"). Splitting the I/O out would break that atomicity (the dedup
short-circuit and the final upsert must see a consistent store).

Per-summary lineage (PIR-872). It is also a
:class:`~pirn.nodes.nested_run_knot.NestedRunKnot`: each level's cluster
summaries run as a nested run — one
:class:`~pirn_agents.specializations.rag.indexing.raptor_summary.RaptorSummary`
per cluster, joined in cluster order by an
:class:`~pirn.nodes.aggregator.Aggregator` — so every LLM summary call has its
own lineage row (knot id ``<prefix>:<level>:<index>``, the id of the node it
produces), ``Result``, and admission through the enclosing run's gate, and the
level's clusters are summarized concurrently. The inner runs inherit the
enclosing run's history, emitters, value plane and execution plane; this
knot's own row names every inner run (``extra["inner_run_ids"]``). The dedup
short-circuit still returns before any inner run starts, and the single final
upsert still happens once, after the last level. As a container this knot
holds no admission slot of its own (its summary leaves take them), so it may
not declare a ``concurrency_group``.

References:
    - Sarthi et al., "RAPTOR" (ICLR 2024): https://arxiv.org/abs/2401.18059
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.retrieval.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.retrieval.vector_stores.vector_record import VectorRecord
from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_summary import RaptorSummary
from pirn_agents.specializations.rag.indexing.raptor_tree import RaptorTree


class RaptorAssembler(Assembler, NestedRunKnot):
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
            ValueError: If ``cluster_size``/``max_levels`` are not positive ints.
        """
        if not isinstance(cluster_size, int) or cluster_size <= 1:
            raise ValueError(
                f"RaptorAssembler: cluster_size must be an int > 1, got {cluster_size!r}"
            )
        if not isinstance(max_levels, int) or max_levels <= 0:
            raise ValueError(
                f"RaptorAssembler: max_levels must be a positive int, got {max_levels!r}"
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
            clusters = [
                tuple(node.text for node in current[start : start + cluster_size])
                for start in range(0, len(current), cluster_size)
            ]
            ids = [f"{prefix}:{level}:{index}" for index in range(len(clusters))]
            summaries = await self._summarize_level(llm, clusters, ids)
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

    async def _summarize_level(
        self, llm: LLMProvider, clusters: list[tuple[str, ...]], ids: list[str]
    ) -> list[str]:
        """Summarize one level's clusters as a nested run, one knot per cluster.

        Args:
            llm: The provider summarizing each cluster.
            clusters: Each cluster's node texts, in tree order.
            ids: The id of the summary node each cluster produces; also the
                id of the knot that summarizes it.

        Returns:
            The summaries, in cluster order.

        Raises:
            SubTapestryError: If any cluster's summary call failed.
        """
        with Tapestry() as inner:
            provider = Parameter("llm", LLMProvider, default=llm, _config=KnotConfig(id="llm"))
            per_cluster: dict[str, Knot] = {
                f"summary_{index}": RaptorSummary(
                    texts=texts, llm=provider, _config=KnotConfig(id=ids[index])
                )
                for index, texts in enumerate(clusters)
            }
            Aggregator(
                combine=RaptorAssembler._in_cluster_order,
                _config=KnotConfig(id="summaries"),
                **per_cluster,
            )
        run = await self._run_inner(inner)
        return run.outputs["summaries"]

    @staticmethod
    def _in_cluster_order(**summaries: str) -> list[str]:
        """Order the per-cluster summaries by their ``summary_<index>`` key."""
        return [summaries[f"summary_{index}"] for index in range(len(summaries))]
