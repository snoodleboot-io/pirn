"""``RaptorTree`` — a built RAPTOR summary tree handle.

The value a RAPTOR build returns: a content-addressed handle describing the tree
that now lives in the vector store. ``content_hash`` keys the tree by its leaf
corpus, so re-ingesting identical content is detected and skipped (``reused``).
Frozen and pydantic-opaque.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode


@dataclass(frozen=True)
class RaptorTree(PirnOpaqueValue):
    """A built RAPTOR tree descriptor.

    Attributes
    ----------
    content_hash:
        SHA-256 (truncated) of the leaf corpus; the tree's content address.
    node_count:
        Total number of tree nodes (leaves + summaries) stored.
    level_count:
        Number of levels, including the leaf level.
    reused:
        ``True`` when the build was skipped because an identical tree already
        existed in the store.
    root:
        The root summary node, or ``None`` for an empty corpus.
    """

    content_hash: str
    node_count: int
    level_count: int
    reused: bool
    root: RaptorNode | None = None
