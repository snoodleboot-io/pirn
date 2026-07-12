"""``ParentChildChunkingStrategy`` — small children under larger parents (F25-S2 / PIR-605).

Splits the text into small, precise child chunks (an internal fixed-size split)
and groups consecutive children under a larger parent. Each emitted child
:class:`Chunk` carries its ``parent_index`` and the full ``parent_text`` in
metadata, so retrieval can match a precise child yet return (or merge up to) the
broader parent context — the small-to-big retrieval pattern shared with F9.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)


class ParentChildChunkingStrategy(ChunkingStrategy):
    """Emit small child chunks tagged with their parent group's text."""

    def __init__(
        self,
        *,
        child_size: int = 400,
        child_overlap: int = 40,
        group_size: int = 3,
    ) -> None:
        """Configure the child splitter and parent grouping.

        Args:
            child_size: Maximum character length of each child chunk. Must be
                positive.
            child_overlap: Characters shared by adjacent children. Must be in
                ``[0, child_size)``.
            group_size: Number of consecutive children per parent. Must be
                positive.

        Raises:
            ValueError: If ``group_size`` is not positive (child sizing is
                validated by the internal fixed-size splitter).
        """
        if group_size <= 0:
            raise ValueError(
                f"ParentChildChunkingStrategy: group_size must be positive, got {group_size!r}"
            )
        self._child_strategy = FixedSizeChunkingStrategy(
            chunk_size=child_size, chunk_overlap=child_overlap
        )
        self._group_size = group_size

    async def chunk(self, text: str) -> list[Chunk]:
        """Split into children and tag each with its parent group's text.

        Args:
            text: The document text to split.

        Returns:
            Ordered child chunks; empty for empty input.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_text("ParentChildChunkingStrategy", text)
        children = await self._child_strategy.chunk(text)
        if not children:
            return []
        texts = [child.text for child in children]
        out: list[Chunk] = []
        for child_index, child_text in enumerate(texts):
            parent_index = child_index // self._group_size
            start = parent_index * self._group_size
            parent_text = "\n".join(texts[start : start + self._group_size])
            out.append(
                Chunk(
                    text=child_text,
                    index=child_index,
                    metadata={
                        "kind": "child",
                        "parent_index": parent_index,
                        "parent_text": parent_text,
                    },
                )
            )
        return out
