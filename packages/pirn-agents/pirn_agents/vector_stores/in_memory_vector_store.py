"""``InMemoryVectorStore`` — the zero-dependency numpy reference store.

The default store for tests and examples: it needs no external service, only
numpy (already in the pirn-core closure). It keeps records in a dict and answers
:meth:`query` with a numpy-vectorised cosine similarity over the (optionally
metadata-filtered) candidate set.

Two search modes:

* **exact** (default) — score every candidate;
* **approximate** — when the candidate set is larger than a probe threshold,
  score a deterministic random subsample (seeded), trading recall for latency.
  A real RAG pipeline runs against this store with no external service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.vector_stores.metadata_match import matches_metadata_filter
from pirn_agents.vector_stores.vector_match import VectorMatch
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class InMemoryVectorStore(VectorMemoryStore):
    """A numpy-backed, in-process reference :class:`VectorMemoryStore`."""

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider | None = None,
        approximate: bool = False,
        probe_size: int = 1024,
        seed: int = 0,
    ) -> None:
        """Initialise an empty in-memory store.

        Args:
            embedder: Optional provider enabling text :meth:`search`.
            approximate: When ``True``, subsample candidates above
                ``probe_size`` instead of scoring them all.
            probe_size: Candidate-count threshold and subsample size for
                approximate mode. Must be a positive integer.
            seed: Seed making approximate subsampling deterministic.

        Raises:
            ValueError: If ``probe_size`` is not a positive integer.
        """
        super().__init__(embedder=embedder)
        if not isinstance(probe_size, int) or probe_size <= 0:
            raise ValueError(f"probe_size must be a positive int, got {probe_size!r}")
        self._records: dict[str, VectorRecord] = {}
        self._approximate: bool = approximate
        self._probe_size: int = probe_size
        self._seed: int = seed

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or overwrite each record by id."""
        for record in records:
            self._records[record.id] = VectorRecord.create(
                id=record.id,
                vector=record.vector,
                metadata=record.metadata,
                document=record.document,
            )

    async def get(self, key: str) -> VectorRecord | None:
        """Return the record stored under ``key``, or ``None``."""
        return self._records.get(key)

    async def delete(self, ids: Sequence[str]) -> None:
        """Remove every record whose id is in ``ids``."""
        for key in ids:
            self._records.pop(key, None)

    async def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return up to ``top_k`` records nearest to ``vector`` by cosine similarity.

        Args:
            vector: The query embedding.
            top_k: Maximum number of hits to return. Must be positive.
            metadata_filter: Optional filter applied before scoring.

        Returns:
            Hits ordered by descending cosine similarity.

        Raises:
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive int, got {top_k!r}")
        candidates = [
            record
            for record in self._records.values()
            if matches_metadata_filter(record.metadata, metadata_filter)
        ]
        candidates = self._select_candidates(candidates)
        if not candidates:
            return []
        matrix: NDArray[np.float64] = np.array(
            [record.vector for record in candidates], dtype=np.float64
        )
        query_vec: NDArray[np.float64] = np.asarray(vector, dtype=np.float64)
        sims = self._cosine_similarities(matrix, query_vec)
        order = np.argsort(-sims)[:top_k]
        return [
            VectorMatch(
                id=candidates[int(i)].id,
                score=float(sims[int(i)]),
                metadata=candidates[int(i)].metadata,
                document=candidates[int(i)].document,
            )
            for i in order
        ]

    def _select_candidates(self, candidates: list[VectorRecord]) -> list[VectorRecord]:
        """Return the full set, or a seeded subsample in approximate mode."""
        if not self._approximate or len(candidates) <= self._probe_size:
            return candidates
        rng = np.random.default_rng(self._seed)
        picks = rng.choice(len(candidates), size=self._probe_size, replace=False)
        return [candidates[int(i)] for i in picks]

    @staticmethod
    def _cosine_similarities(
        matrix: NDArray[np.float64], query_vec: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Return the cosine similarity of each matrix row to ``query_vec``."""
        row_norms = np.linalg.norm(matrix, axis=1)
        query_norm = float(np.linalg.norm(query_vec))
        denom = row_norms * query_norm
        denom[denom == 0.0] = 1.0
        return (matrix @ query_vec) / denom

    async def close(self) -> None:
        """Drop all records and scrub credentials."""
        self._records.clear()
        self._clear_credentials()
