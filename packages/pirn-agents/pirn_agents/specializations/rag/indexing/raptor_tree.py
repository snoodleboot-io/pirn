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

    def __post_init__(self) -> None:
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise TypeError(
                f"RaptorTree: content_hash must be a non-empty str, got {self.content_hash!r}"
            )
        if not isinstance(self.node_count, int) or isinstance(self.node_count, bool):
            raise TypeError(
                f"RaptorTree: node_count must be an int, got {type(self.node_count).__name__}"
            )
        if self.node_count < 0:
            raise ValueError(f"RaptorTree: node_count must be >= 0, got {self.node_count!r}")
        if not isinstance(self.level_count, int) or isinstance(self.level_count, bool):
            raise TypeError(
                f"RaptorTree: level_count must be an int, got {type(self.level_count).__name__}"
            )
        if self.level_count < 0:
            raise ValueError(f"RaptorTree: level_count must be >= 0, got {self.level_count!r}")
        if not isinstance(self.reused, bool):
            raise TypeError(f"RaptorTree: reused must be a bool, got {type(self.reused).__name__}")
        if self.root is not None and not isinstance(self.root, RaptorNode):
            raise TypeError(
                f"RaptorTree: root must be a RaptorNode or None, got {type(self.root).__name__}"
            )
