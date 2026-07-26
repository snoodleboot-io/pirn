"""``VectorMatch`` — one scored hit returned by a vector query.

The neutral read unit every
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore`
returns from :meth:`query`. Frozen and opaque; ``score`` is a similarity where
larger is more similar (cosine similarity for the in-memory reference).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class VectorMatch(PirnOpaqueValue):
    """A single scored vector-search hit.

    Attributes
    ----------
    id:
        The matched record's primary key.
    score:
        Similarity score; larger means more similar.
    metadata:
        The matched record's metadata.
    document:
        The matched record's source text, if any.
    """

    id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)
    document: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise TypeError(f"VectorMatch: id must be a non-empty str, got {self.id!r}")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise TypeError(f"VectorMatch: score must be a real number, got {self.score!r}")
        # Scores are similarities in the cosine range; a small tolerance absorbs
        # floating-point drift at the boundary (e.g. a self-match rounding to
        # 1.0000000002) while still rejecting gross errors, NaN, and infinities.
        tolerance = 1e-6
        if not (-1.0 - tolerance <= self.score <= 1.0 + tolerance):
            raise ValueError(f"VectorMatch: score must be within [-1.0, 1.0], got {self.score!r}")
        if not isinstance(self.metadata, Mapping):
            raise TypeError(
                f"VectorMatch: metadata must be a mapping, got {type(self.metadata).__name__}"
            )
        if self.document is not None and not isinstance(self.document, str):
            raise TypeError(
                f"VectorMatch: document must be a str or None, got {type(self.document).__name__}"
            )
