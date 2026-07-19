"""``SemanticChunkingStrategy`` — embedding-similarity boundaries (F25-S2 / PIR-605).

Segments the text into sentences, embeds each via a caller-supplied
:class:`EmbeddingProvider`, and starts a new chunk wherever the cosine
*distance* between consecutive sentences exceeds a breakpoint threshold — i.e.
where the topic shifts. Boundaries follow meaning rather than a fixed length.
Only numpy (in the core closure) is used for the vector math; the embedding
backend is whatever provider the caller injects, so this strategy stays
provider-neutral and fully testable with a stub embedder.
"""

from __future__ import annotations

import re

import numpy as np
from numpy.typing import NDArray

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)


class SemanticChunkingStrategy(ChunkingStrategy):
    """Split text at sentence boundaries where embedding similarity drops."""

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        breakpoint_distance: float = 0.5,
        max_sentences: int | None = None,
    ) -> None:
        """Configure the semantic splitter.

        Args:
            embedder: Provider used to embed each sentence.
            breakpoint_distance: Cosine distance (``1 - similarity``, in
                ``[0, 2]``) above which a new chunk starts. Must be in ``[0, 2]``.
            max_sentences: Optional hard cap on sentences per chunk, forcing a
                break even without a semantic boundary. Must be positive if set.

        Raises:
            TypeError: If ``embedder`` is not an :class:`EmbeddingProvider`.
            ValueError: If ``breakpoint_distance`` or ``max_sentences`` is invalid.
        """
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"SemanticChunkingStrategy: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not 0.0 <= breakpoint_distance <= 2.0:
            raise ValueError(
                "SemanticChunkingStrategy: breakpoint_distance must be in [0, 2], "
                f"got {breakpoint_distance!r}"
            )
        if max_sentences is not None and max_sentences <= 0:
            raise ValueError(
                f"SemanticChunkingStrategy: max_sentences must be positive, got {max_sentences!r}"
            )
        self._embedder = embedder
        self._breakpoint_distance = breakpoint_distance
        self._max_sentences = max_sentences

    async def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` at semantic breakpoints between sentences.

        Args:
            text: The document text to split.

        Returns:
            Ordered chunks; empty for empty input, a single chunk for one
            sentence.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("SemanticChunkingStrategy", text)
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            return [
                Chunk(
                    text=sentences[0], index=0, metadata={"sentence_start": 0, "sentence_count": 1}
                )
            ]
        vectors = await self._embedder.embed(sentences)
        distances = self._consecutive_distances(vectors)
        return self._group(sentences, distances)

    def _group(self, sentences: list[str], distances: list[float]) -> list[Chunk]:
        """Accumulate sentences into chunks, breaking on distance or the cap."""
        chunks: list[Chunk] = []
        current: list[str] = [sentences[0]]
        start = 0
        for offset, sentence in enumerate(sentences[1:], start=1):
            over_cap = self._max_sentences is not None and len(current) >= self._max_sentences
            boundary = distances[offset - 1] > self._breakpoint_distance
            if over_cap or boundary:
                chunks.append(self._make_chunk(current, len(chunks), start))
                current = []
                start = offset
            current.append(sentence)
        if current:
            chunks.append(self._make_chunk(current, len(chunks), start))
        return chunks

    @staticmethod
    def _make_chunk(sentences: list[str], index: int, start: int) -> Chunk:
        """Build a :class:`Chunk` from a run of sentences."""
        return Chunk(
            text=" ".join(sentences),
            index=index,
            metadata={"sentence_start": start, "sentence_count": len(sentences)},
        )

    @staticmethod
    def _consecutive_distances(vectors: list[list[float]]) -> list[float]:
        """Return the cosine distance between each pair of consecutive vectors."""
        matrix: NDArray[np.float64] = np.asarray(vectors, dtype=np.float64)
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1.0
        unit = matrix / norms[:, None]
        similarities = np.sum(unit[:-1] * unit[1:], axis=1)
        return [float(1.0 - value) for value in similarities]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split ``text`` into sentences on terminal punctuation boundaries."""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [part.strip() for part in parts if part.strip()]
