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
