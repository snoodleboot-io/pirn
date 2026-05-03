"""``_DocumentChunker`` — internal helper Knot for :class:`DocumentIngestionPipeline`.

Splits text into overlapping fixed-size chunks. Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _DocumentChunker(Knot):
    """Split text into overlapping fixed-size chunks."""

    def __init__(
        self,
        *,
        text: Knot | str,
        chunk_size: int,
        chunk_overlap: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        **_: Any,
    ) -> list[str]:
        """Split text into overlapping fixed-size chunks and return the list.

        Args:
            text: The source text to split into chunks.
            chunk_size: The maximum character length of each chunk.
            chunk_overlap: The number of characters that adjacent chunks share.

        Returns:
            A list of text chunk strings; empty if the input text is empty.

        Raises:
            ValueError: If chunk_size is not positive or chunk_overlap is out of range.
        """
        if chunk_size <= 0:
            raise ValueError(
                "DocumentIngestionPipeline: chunk_size must be positive, "
                f"got {chunk_size!r}"
            )
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "DocumentIngestionPipeline: chunk_overlap must be in "
                f"[0, chunk_size), got {chunk_overlap!r}"
            )
        if not text:
            return []
        stride = chunk_size - chunk_overlap
        chunks: list[str] = []
        position = 0
        length = len(text)
        while position < length:
            end = min(position + chunk_size, length)
            chunks.append(text[position:end])
            if end == length:
                break
            position += stride
        return chunks
