"""``RaptorLevelState`` — the value threaded through the RAPTOR level climb.

A :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`: it carries the live
provider and embedder each level needs, neither of which is describable to
pydantic. Holding them on the loop instead would be graph state shared by every
run of the tapestry (knot-design-rules Rule 4).

Internal API. See ``raptor_level_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider
from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode


@dataclass(frozen=True)
class RaptorLevelState(PirnOpaqueValue):
    """One tree level's worth of accumulated build state.

    Frozen; the loop returns a new instance rather than mutating.

    Attributes:
        llm: The provider summarizing each cluster.
        embedder: The provider embedding each level's summaries.
        prefix: The content-addressed node-id prefix, ``raptor:<hash>``.
        cluster_size: Number of consecutive nodes per cluster.
        max_levels: Maximum number of summary levels above the leaves.
        level: The level just built; ``0`` is the leaves.
        current: The level's nodes, in tree order — what the next level
            clusters.
        nodes: Every node built so far, in tree order, leaves first.
    """

    llm: LLMProvider
    embedder: EmbeddingProvider
    prefix: str
    cluster_size: int
    max_levels: int
    level: int
    current: tuple[RaptorNode, ...]
    nodes: tuple[RaptorNode, ...]

    def with_fields(self, **changes: Any) -> RaptorLevelState:
        """Return a copy with ``changes`` applied."""
        return replace(self, **changes)

    def clusters(self) -> tuple[tuple[str, ...], ...]:
        """Group the current level's texts into consecutive clusters, in tree order."""
        return tuple(
            tuple(node.text for node in self.current[start : start + self.cluster_size])
            for start in range(0, len(self.current), self.cluster_size)
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the lineage-relevant fields, leaving the live collaborators out."""
        return {
            "prefix": self.prefix,
            "cluster_size": self.cluster_size,
            "max_levels": self.max_levels,
            "level": self.level,
            "current_size": len(self.current),
            "node_count": len(self.nodes),
        }
