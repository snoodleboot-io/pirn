"""``_ChunkPositions`` — the position labels the chunk summariser fans out over.

The per-chunk prompt embeds ``"Chunk {i} of {n}"``, but core's ``Map`` marker
injects **only the element** — no index, no total (``knot.py:551``). So the
fan-out is a ``ZipMap`` over two collections, and this knot produces the second:
one rendered label per chunk, in chunk order.

Changing the prompt to drop the index would remove the need for this knot, and
is not an option — WS6's prompt pins assert that text.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _ChunkPositions(Knot):
    """Render ``"Chunk i of n"`` for each chunk, preserving order."""

    def __init__(
        self,
        *,
        chunks: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunks=chunks, _config=_config, **kwargs)

    async def process(self, chunks: list[str], **_: Any) -> list[str]:
        """Build one position label per chunk.

        Args:
            chunks: The chunks about to be summarised.

        Returns:
            Labels in chunk order; empty when there are no chunks, which
            gives the ``ZipMap`` zero invocations.
        """
        total = len(chunks)
        return [f"Chunk {index + 1} of {total}" for index in range(total)]
