"""``RaptorNode`` — one node in a RAPTOR hierarchical summary tree.

A node is either a leaf chunk (level 0) or an LLM-generated summary of a cluster
of lower-level nodes. It is frozen and pydantic-opaque so it travels through the
pirn graph by identity, like the other vector-store value types.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RaptorNode(PirnOpaqueValue):
    """A single RAPTOR tree node.

    Attributes
    ----------
    id:
        Stable content-addressed node id (``raptor:<hash>:<level>:<index>``).
    level:
        Tree level; ``0`` for leaf chunks, higher for summaries.
    text:
        The node text — a raw chunk at level 0, else a cluster summary.
    vector:
        The node embedding, stored as an immutable tuple of floats.
    """

    id: str
    level: int
    text: str
    vector: tuple[float, ...]

    @classmethod
    def create(cls, *, id: str, level: int, text: str, vector: Sequence[float]) -> RaptorNode:
        """Build a node, normalising the vector to an immutable tuple.

        Args:
            id: The node id.
            level: The tree level (0 for leaves).
            text: The node text.
            vector: Any float sequence; coerced to a tuple.

        Returns:
            A frozen :class:`RaptorNode`.
        """
        return cls(id=id, level=level, text=text, vector=tuple(float(x) for x in vector))
