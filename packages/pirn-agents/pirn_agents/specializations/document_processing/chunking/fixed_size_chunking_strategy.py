"""``FixedSizeChunkingStrategy`` — overlapping fixed-size windows (F25-S2 / PIR-600).

The formalized, public form of the internal fixed-size sliding-window splitter:
it strides a window of ``chunk_size`` characters across the text by
``chunk_size - chunk_overlap``, emitting one :class:`Chunk` per window with its
character offsets recorded in metadata.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)


class FixedSizeChunkingStrategy(ChunkingStrategy):
    """Split text into overlapping fixed-size character windows."""

    def __init__(self, *, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        """Configure the window size and overlap.

        Args:
            chunk_size: Maximum character length of each chunk. Must be positive.
            chunk_overlap: Characters shared by adjacent chunks. Must be in
                ``[0, chunk_size)``.

        Raises:
            ValueError: If ``chunk_size`` is not positive or ``chunk_overlap`` is
                out of range.
        """
        if chunk_size <= 0:
            raise ValueError(
                f"FixedSizeChunkingStrategy: chunk_size must be positive, got {chunk_size!r}"
            )
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "FixedSizeChunkingStrategy: chunk_overlap must be in "
                f"[0, chunk_size), got {chunk_overlap!r}"
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` into overlapping fixed-size chunks.

        Args:
            text: The document text to split.

        Returns:
            Ordered chunks; empty when ``text`` is empty.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("FixedSizeChunkingStrategy", text)
        if not text:
            return []
        stride = self._chunk_size - self._chunk_overlap
        chunks: list[Chunk] = []
        position = 0
        length = len(text)
        index = 0
        while position < length:
            end = min(position + self._chunk_size, length)
            chunks.append(
                Chunk(
                    text=text[position:end],
                    index=index,
                    metadata={"start_char": position, "end_char": end},
                )
            )
            index += 1
            if end == length:
                break
            position += stride
        return chunks
