"""``SentenceWindowChunkingStrategy`` — overlapping sentence windows (F25-S2 / PIR-600).

Segments the text into sentences (a lightweight stdlib regex on terminal
punctuation — no NLP backend) then slides a window of ``window_size`` sentences
across them by ``window_size - window_overlap``. Each chunk is a run of whole
sentences, which keeps retrieval snippets readable and self-contained.
"""

from __future__ import annotations

import re

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)


class SentenceWindowChunkingStrategy(ChunkingStrategy):
    """Split text into overlapping windows of whole sentences."""

    def __init__(self, *, window_size: int = 3, window_overlap: int = 1) -> None:
        """Configure the sentence window.

        Args:
            window_size: Number of sentences per chunk. Must be positive.
            window_overlap: Sentences shared by adjacent windows. Must be in
                ``[0, window_size)``.

        Raises:
            ValueError: If ``window_size`` is not positive or ``window_overlap``
                is out of range.
        """
        if window_size <= 0:
            raise ValueError(
                f"SentenceWindowChunkingStrategy: window_size must be positive, got {window_size!r}"
            )
        if window_overlap < 0 or window_overlap >= window_size:
            raise ValueError(
                "SentenceWindowChunkingStrategy: window_overlap must be in "
                f"[0, window_size), got {window_overlap!r}"
            )
        self._window_size = window_size
        self._window_overlap = window_overlap

    async def chunk(self, text: str) -> list[Chunk]:
        """Segment into sentences and window them.

        Args:
            text: The document text to split.

        Returns:
            Ordered chunks, each a run of whole sentences; empty for empty input.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("SentenceWindowChunkingStrategy", text)
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        stride = self._window_size - self._window_overlap
        chunks: list[Chunk] = []
        index = 0
        position = 0
        total = len(sentences)
        while position < total:
            window = sentences[position : position + self._window_size]
            chunks.append(
                Chunk(
                    text=" ".join(window),
                    index=index,
                    metadata={
                        "sentence_start": position,
                        "sentence_count": len(window),
                    },
                )
            )
            index += 1
            if position + self._window_size >= total:
                break
            position += stride
        return chunks

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split ``text`` into sentences on terminal punctuation boundaries."""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [part.strip() for part in parts if part.strip()]
