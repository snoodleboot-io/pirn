"""``Chunk`` — one text span emitted by a chunking strategy (F25-S2 / PIR-575).

The neutral output unit of the chunking library: a frozen, opaque span carrying
its ordinal ``index`` within the document plus strategy-specific ``metadata``
(e.g. sentence range, parent id/text for parent-child, char offsets). Downstream
embedding/upsert depends only on this shape, so any strategy is interchangeable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class Chunk(PirnOpaqueValue):
    """One chunk of a document.

    Attributes
    ----------
    text:
        The chunk's text span.
    index:
        Zero-based ordinal of this chunk within the document.
    metadata:
        Strategy-specific scalar metadata (e.g. ``parent_index``,
        ``sentence_start``, ``kind``); empty by default.
    """

    text: str
    index: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError(f"Chunk: text must be a str, got {type(self.text).__name__}")
        if not self.text:
            raise ValueError("Chunk: text must be non-empty")
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise TypeError(f"Chunk: index must be an int, got {type(self.index).__name__}")
        if self.index < 0:
            raise ValueError(f"Chunk: index must be >= 0, got {self.index!r}")
        if not isinstance(self.metadata, Mapping):
            raise TypeError(
                f"Chunk: metadata must be a mapping, got {type(self.metadata).__name__}"
            )
