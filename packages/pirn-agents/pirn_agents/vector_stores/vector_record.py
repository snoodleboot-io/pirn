"""``VectorRecord`` — one upsertable (id, vector, metadata, document) tuple.

The neutral write unit every :class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore`
accepts. Frozen and opaque so it travels through the pirn graph without
entering the content-addressed hash by value; the vector is normalised to a
tuple so records are immutable and hashable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class VectorRecord(PirnOpaqueValue):
    """A single vector-store record.

    Attributes
    ----------
    id:
        Stable primary key; upserting an existing ``id`` overwrites it.
    vector:
        The dense embedding, stored as an immutable tuple of floats.
    metadata:
        Arbitrary scalar metadata used for equality/membership filtering.
    document:
        Optional original text the vector was derived from.
    """

    id: str
    vector: tuple[float, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    document: str | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        vector: Sequence[float],
        metadata: Mapping[str, Any] | None = None,
        document: str | None = None,
    ) -> VectorRecord:
        """Build a record from any float sequence, normalising the vector.

        Args:
            id: The record primary key.
            vector: Any sequence of floats; coerced to an immutable tuple.
            metadata: Optional metadata mapping; defaults to empty.
            document: Optional source text.

        Returns:
            A frozen :class:`VectorRecord`.
        """
        return cls(
            id=id,
            vector=tuple(float(x) for x in vector),
            metadata=dict(metadata) if metadata is not None else {},
            document=document,
        )
