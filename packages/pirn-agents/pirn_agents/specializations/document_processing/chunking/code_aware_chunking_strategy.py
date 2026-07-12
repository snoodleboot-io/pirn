"""``CodeAwareChunkingStrategy`` — split source on structural boundaries (F25-S2 / PIR-605).

Splits source code at top-level definition boundaries (``def``/``class``/
``function``/``func`` and common access modifiers at column zero) rather than
mid-statement, then merges adjacent blocks up to ``max_chars`` so a chunk holds
whole functions/classes wherever they fit. Uses only the stdlib :mod:`re`; pair
it with :class:`CodeLoader` (F25-S1). The heuristic is language-agnostic and
does not depend on a full parser.
"""

from __future__ import annotations

import re

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)


class CodeAwareChunkingStrategy(ChunkingStrategy):
    """Split code at definition boundaries, merging blocks up to a size cap."""

    def __init__(self, *, max_chars: int = 1500) -> None:
        """Configure the size cap.

        Args:
            max_chars: Maximum character length of a merged chunk. Must be
                positive.

        Raises:
            ValueError: If ``max_chars`` is not positive.
        """
        if max_chars <= 0:
            raise ValueError(
                f"CodeAwareChunkingStrategy: max_chars must be positive, got {max_chars!r}"
            )
        self._max_chars = max_chars
        self._boundary = re.compile(
            r"^(async def |def |class |func |function |public |private |protected |static )"
        )

    async def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` at definition boundaries and merge up to the cap.

        Args:
            text: The source code to split.

        Returns:
            Ordered chunks, each holding one or more whole top-level blocks;
            empty for empty input.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("CodeAwareChunkingStrategy", text)
        if not text.strip():
            return []
        blocks = self._blocks(text)
        merged = self._merge(blocks)
        return [
            Chunk(text=span, index=index, metadata={"length": len(span)})
            for index, span in enumerate(merged)
        ]

    def _blocks(self, text: str) -> list[str]:
        """Split ``text`` into blocks starting at each top-level definition."""
        blocks: list[str] = []
        current: list[str] = []
        for line in text.split("\n"):
            if current and self._boundary.match(line):
                blocks.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            blocks.append("\n".join(current))
        return [block for block in blocks if block.strip()]

    def _merge(self, blocks: list[str]) -> list[str]:
        """Greedily merge adjacent blocks up to ``max_chars``."""
        chunks: list[str] = []
        current = ""
        for block in blocks:
            candidate = f"{current}\n\n{block}" if current else block
            if current and len(candidate) > self._max_chars:
                chunks.append(current)
                current = block
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks
