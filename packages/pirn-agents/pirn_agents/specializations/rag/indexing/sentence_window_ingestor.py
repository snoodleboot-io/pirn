"""``SentenceWindowIngestor`` — index single sentences with a neighbour window.

Sentence-window retrieval embeds each *sentence* on its own (maximally precise
matching) but stores the surrounding sentence *window* as metadata so retrieval
can hand the synthesizer local context around the exact hit. Sentence
segmentation is an indexing-specific concern here (not a general chunking
library): a minimal punctuation splitter produces the sentence units.

Algorithm:
    1. Validate ``text`` (str), ``embedder``, ``store``, ``doc_id`` (str), and
       ``window_size`` (non-negative int).
    2. Split ``text`` into sentences.
    3. Embed each sentence and upsert one record per sentence with metadata
       ``{window, position, kind}`` where ``window`` is the ``±window_size``
       neighbour join.
    4. Return the number of sentence records written.

References:
    - Sentence-window node parser (LlamaIndex).
"""

from __future__ import annotations

import re
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.embedding_provider import EmbeddingProvider

from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class SentenceWindowIngestor(Knot):
    """Embed each sentence and store its neighbour window as metadata."""

    def __init__(
        self,
        *,
        text: Knot | str,
        embedder: Knot | EmbeddingProvider,
        store: Knot | VectorMemoryStore,
        doc_id: Knot | str,
        _config: KnotConfig,
        window_size: Knot | int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            embedder=embedder,
            store=store,
            doc_id=doc_id,
            window_size=window_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        embedder: EmbeddingProvider,
        store: VectorMemoryStore,
        doc_id: str,
        window_size: int = 1,
        **_: Any,
    ) -> int:
        """Index each sentence with its neighbour window and return the count.

        Args:
            text: The full source document to split into sentences.
            embedder: The provider embedding each sentence.
            store: The vector store receiving the sentence records.
            doc_id: The source document id used for stable record keys.
            window_size: Number of neighbour sentences on each side of the window.

        Returns:
            The number of sentence records upserted.

        Raises:
            TypeError: If ``text``/``doc_id`` are not strings or ``embedder``/
                ``store`` are the wrong type.
            ValueError: If ``window_size`` is negative.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"SentenceWindowIngestor: text must be a string, got {type(text).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"SentenceWindowIngestor: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"SentenceWindowIngestor: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(doc_id, str):
            raise TypeError(
                f"SentenceWindowIngestor: doc_id must be a string, got {type(doc_id).__name__}"
            )
        if not isinstance(window_size, int) or window_size < 0:
            raise ValueError(
                f"SentenceWindowIngestor: window_size must be a non-negative int, "
                f"got {window_size!r}"
            )
        sentences = _split_sentences(text)
        if not sentences:
            return 0
        vectors = await embedder.embed(sentences)
        records: list[VectorRecord] = []
        for position, sentence in enumerate(sentences):
            start = max(0, position - window_size)
            end = min(len(sentences), position + window_size + 1)
            window = " ".join(sentences[start:end])
            records.append(
                VectorRecord.create(
                    id=f"{doc_id}:sent:{position}",
                    vector=vectors[position],
                    metadata={"window": window, "position": position, "kind": "sentence"},
                    document=sentence,
                )
            )
        await store.upsert(records)
        return len(records)


def _split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences on terminal punctuation, dropping blanks."""
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]
