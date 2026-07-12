"""``RecursiveCharacterChunkingStrategy`` — separator-aware splitting (F25-S2 / PIR-600).

Splits on a descending hierarchy of separators (paragraphs, then lines, then
words, then characters), recursing into any piece that still exceeds
``chunk_size``, then greedily merges the small pieces back up to ``chunk_size``
with a bounded ``chunk_overlap`` tail. This keeps semantic boundaries intact far
better than a blind fixed-size window while still bounding chunk length.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)


class RecursiveCharacterChunkingStrategy(ChunkingStrategy):
    """Split text along a separator hierarchy, merging pieces up to a size cap."""

    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        separators: Sequence[str] = ("\n\n", "\n", " ", ""),
    ) -> None:
        """Configure the size cap, overlap, and separator hierarchy.

        Args:
            chunk_size: Maximum character length of a merged chunk. Must be
                positive.
            chunk_overlap: Maximum characters of trailing context carried into
                the next chunk. Must be in ``[0, chunk_size)``.
            separators: Ordered separators tried from coarsest to finest; the
                final ``""`` forces a hard character split.

        Raises:
            ValueError: If sizes are invalid or ``separators`` is empty.
        """
        if chunk_size <= 0:
            raise ValueError(
                f"RecursiveCharacterChunkingStrategy: chunk_size must be positive, got {chunk_size!r}"
            )
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "RecursiveCharacterChunkingStrategy: chunk_overlap must be in "
                f"[0, chunk_size), got {chunk_overlap!r}"
            )
        if not separators:
            raise ValueError("RecursiveCharacterChunkingStrategy: separators must be non-empty")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = tuple(separators)

    async def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` recursively and merge pieces up to the size cap.

        Args:
            text: The document text to split.

        Returns:
            Ordered chunks; empty when ``text`` is empty.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("RecursiveCharacterChunkingStrategy", text)
        if not text:
            return []
        pieces = self._split(text, list(self._separators))
        merged = self._merge(pieces)
        return [
            Chunk(text=span, index=index, metadata={"length": len(span)})
            for index, span in enumerate(merged)
        ]

    def _split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split ``text`` until every piece fits ``chunk_size``."""
        if len(text) <= self._chunk_size:
            return [text] if text else []
        separator = separators[0] if separators else ""
        remaining = separators[1:]
        if separator == "":
            step = self._chunk_size
            return [text[i : i + step] for i in range(0, len(text), step)]
        out: list[str] = []
        for part in text.split(separator):
            if not part:
                continue
            if len(part) <= self._chunk_size:
                out.append(part)
            else:
                out.extend(self._split(part, remaining))
        return out

    def _merge(self, pieces: list[str]) -> list[str]:
        """Greedily merge small pieces up to ``chunk_size`` with overlap tails."""
        chunks: list[str] = []
        current: list[str] = []
        for piece in pieces:
            if current and len(" ".join([*current, piece])) > self._chunk_size:
                chunks.append(" ".join(current))
                current = self._overlap_tail(current)
            current.append(piece)
        if current:
            chunks.append(" ".join(current))
        return chunks

    def _overlap_tail(self, pieces: list[str]) -> list[str]:
        """Return the trailing pieces whose joined length fits ``chunk_overlap``."""
        if self._chunk_overlap <= 0:
            return []
        tail: list[str] = []
        for piece in reversed(pieces):
            if tail and len(" ".join([piece, *tail])) > self._chunk_overlap:
                break
            tail.insert(0, piece)
        return tail
