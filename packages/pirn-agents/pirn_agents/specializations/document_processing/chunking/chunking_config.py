"""``ChunkingConfig`` — the default chunk geometry for document processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ChunkingConfig(PirnOpaqueValue):
    """The stock character window a document is split into, plus its overlap.

    Chunk size and overlap are one decision, not two: the overlap only makes
    sense relative to the window it stitches together, and a strategy, an
    ingestion pipeline, and a QA pipeline that split the *same* documents must
    agree or their chunk ids stop lining up. This frozen value is the single
    declaration all of them read; pipelines that deliberately want a different
    geometry (summarisation's wider window, RAPTOR's small leaves) pass their
    own numbers explicitly, which now reads as the deviation it is.

    Attributes
    ----------
    chunk_size:
        Maximum characters per chunk. Must be >= 1. Defaults to 1000.
    chunk_overlap:
        Characters each chunk shares with its predecessor, preserving context
        across a boundary. Must be non-negative and smaller than ``chunk_size``.
        Defaults to 100.
    """

    chunk_size: int = 1000
    chunk_overlap: int = 100

    def __post_init__(self) -> None:
        """Validate the window and its overlap.

        Raises:
            ValueError: If ``chunk_size`` is not an int >= 1, if
                ``chunk_overlap`` is not a non-negative int, or if the overlap
                is not smaller than the window (which would never advance).
        """
        if (
            isinstance(self.chunk_size, bool)
            or not isinstance(self.chunk_size, int)
            or self.chunk_size < 1
        ):
            raise ValueError(
                f"ChunkingConfig: chunk_size must be an int >= 1, got {self.chunk_size!r}"
            )
        if (
            isinstance(self.chunk_overlap, bool)
            or not isinstance(self.chunk_overlap, int)
            or self.chunk_overlap < 0
        ):
            raise ValueError(
                f"ChunkingConfig: chunk_overlap must be a non-negative int, "
                f"got {self.chunk_overlap!r}"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"ChunkingConfig: chunk_overlap must be smaller than chunk_size, "
                f"got {self.chunk_overlap!r} >= {self.chunk_size!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"chunk_size": self.chunk_size, "chunk_overlap": self.chunk_overlap}
