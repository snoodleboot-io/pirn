"""``IncrementalUpserter`` — content-hash change detection + delta re-embed (F25-S4 / PIR-623).

Keeps a per-document *manifest* (the ordered list of chunk content hashes and
the last-indexed timestamp) in the same :class:`MemoryStore` as the chunk
records. On each re-index it diffs the freshly chunked content against the
manifest and:

* embeds and stores ONLY new/changed chunks (delta),
* deletes records for removed chunk hashes,
* refreshes the manifest timestamp (resetting the TTL clock).

Re-index cost therefore scales with the change volume, not the corpus size. The
store is content-addressed by ``{doc_id}:{chunk_hash}`` so an unchanged chunk
keeps its key and is never re-embedded.

Why the writes are sequential (PIR-874)
---------------------------------------
``upsert`` used to fan its writes and its deletes out with two
``asyncio.gather`` calls: a second scheduler beside the engine, and — because
``gather`` is unbounded — N concurrent store writes for a document with N
changed chunks, however small ``IngestionRunner``'s ``max_concurrency`` was.
The engine is the one scheduler, so they are awaited one at a time instead.

The cost lands where there is least of it. This is the *incremental* path: by
construction ``plan.to_embed`` holds only the chunks whose content changed, so
a steady-state re-index writes a handful. The bulk path keeps its real
concurrency — :class:`~pirn_agents.specializations.document_processing.embedding_indexer.EmbeddingIndexer`
declares one ``StoredChunkEmbedding`` knot per chunk and lets the engine run
them.

Asking the engine for concurrency here instead would mean one knot per write,
which makes :class:`~pirn_agents.specializations.document_processing.document_ingest.DocumentIngest`
a container — and a container holds no admission slot, so it could no longer be
a member of the ``ingest_docs`` group and ``max_concurrency`` would stop
bounding documents. That is a change to a documented public parameter, so it is
not made here.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.incremental.freshness_policy import (
    FreshnessPolicy,
)
from pirn_agents.specializations.document_processing.incremental.upsert_plan import (
    UpsertPlan,
)


class IncrementalUpserter(PirnOpaqueValue):
    """Diff-and-upsert a document's chunks by content hash into a memory store."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        embedder: EmbeddingProvider,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Bind the upserter to a store, embedder, and clock.

        Args:
            store: The memory store holding chunk records and per-doc manifests.
            embedder: The provider used to embed new/changed chunks.
            clock: Zero-arg epoch-seconds source for index timestamps; defaults
                to :func:`time.time`.

        Raises:
            TypeError: If ``store``/``embedder`` are the wrong type.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"IncrementalUpserter: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"IncrementalUpserter: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        self._store = store
        self._embedder = embedder
        self._clock = clock if clock is not None else time.time

    async def plan(self, doc_id: str, chunks: Sequence[Chunk]) -> UpsertPlan:
        """Diff ``chunks`` against the stored manifest without writing anything.

        Args:
            doc_id: The document being (re-)indexed.
            chunks: The freshly produced chunks for the document.

        Returns:
            The :class:`UpsertPlan` partitioning chunks into embed/unchanged/
            removed.
        """
        manifest = await self._store.retrieve(self._manifest_key(doc_id))
        old_hashes: list[str] = list(manifest["chunk_hashes"]) if manifest else []
        old_set = set(old_hashes)
        seen: set[str] = set()
        manifest_hashes: list[str] = []
        to_embed: list[Chunk] = []
        unchanged: list[str] = []
        for chunk in chunks:
            content_hash = self._hash(chunk.text)
            if content_hash in seen:
                continue  # identical content within the doc maps to one record
            seen.add(content_hash)
            manifest_hashes.append(content_hash)
            if content_hash in old_set:
                unchanged.append(content_hash)
            else:
                to_embed.append(chunk)
        removed = [content_hash for content_hash in old_hashes if content_hash not in seen]
        return UpsertPlan(
            doc_id=doc_id,
            to_embed=tuple(to_embed),
            unchanged_hashes=tuple(unchanged),
            removed_hashes=tuple(removed),
            manifest_hashes=tuple(manifest_hashes),
        )

    async def upsert(self, doc_id: str, chunks: Sequence[Chunk]) -> UpsertPlan:
        """Execute the delta plan: embed new chunks, delete stale, refresh manifest.

        Args:
            doc_id: The document being (re-)indexed.
            chunks: The freshly produced chunks for the document.

        Returns:
            The executed :class:`UpsertPlan` (its counts describe what changed).

        Note:
            The writes and deletes are awaited one at a time: the engine is the
            one scheduler (PIR-874). See the module docstring for why that costs
            little on this path and what asking the engine for concurrency
            instead would cost.
        """
        plan = await self.plan(doc_id, chunks)
        now = self._clock()
        if plan.to_embed:
            vectors = await self._embedder.embed([chunk.text for chunk in plan.to_embed])
            for chunk, vector in zip(plan.to_embed, vectors, strict=True):
                content_hash = self._hash(chunk.text)
                await self._store.store(
                    self._chunk_key(doc_id, content_hash),
                    {
                        "doc_id": doc_id,
                        "chunk_hash": content_hash,
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "embedding": list(vector),
                        "indexed_at": now,
                        "metadata": dict(chunk.metadata),
                    },
                )
        for content_hash in plan.removed_hashes:
            await self._store.forget(self._chunk_key(doc_id, content_hash))
        await self._store.store(
            self._manifest_key(doc_id),
            {"chunk_hashes": list(plan.manifest_hashes), "indexed_at": now},
        )
        return plan

    async def indexed_at(self, doc_id: str) -> float | None:
        """Return the last-indexed epoch time for ``doc_id``, or ``None``."""
        manifest = await self._store.retrieve(self._manifest_key(doc_id))
        if manifest is None:
            return None
        value = manifest.get("indexed_at")
        return float(value) if value is not None else None

    async def is_stale(self, doc_id: str, policy: FreshnessPolicy, now: float) -> bool:
        """Return whether ``doc_id`` is stale under ``policy`` at ``now``.

        A never-indexed document is treated as stale so it gets ingested.
        """
        indexed_at = await self.indexed_at(doc_id)
        if indexed_at is None:
            return True
        return policy.is_stale(indexed_at, now)

    @staticmethod
    def _hash(text: str) -> str:
        """Return core's canonical content hash of a chunk's text."""
        return ContentHasher.hash(text, strict=True)

    @staticmethod
    def _manifest_key(doc_id: str) -> str:
        """Return the manifest key for ``doc_id``."""
        return f"{doc_id}:manifest"

    @staticmethod
    def _chunk_key(doc_id: str, content_hash: str) -> str:
        """Return the content-addressed record key for a chunk."""
        return f"{doc_id}:{content_hash}"
