"""``TraversalBudget`` — the depth / fanout / size bounds on a graph traversal.

A frozen, hashable value that bounds how far and how wide
:class:`~pirn_agents.graph_rag.graph_traversal.GraphTraversal` expands, so a
subgraph retrieval stays cheap and predictable even over a large graph:

* ``max_depth`` — the number of hops from the seed set;
* ``max_fanout`` — the per-node neighbor cap applied at each hop;
* ``max_nodes`` — the total node budget for the whole traversal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraversalBudget:
    """Depth / fanout / total-size bounds for a bounded graph traversal.

    Attributes
    ----------
    max_depth:
        Maximum number of hops expanded from the seed set.
    max_fanout:
        Maximum neighbors expanded per node at each hop.
    max_nodes:
        Maximum total number of nodes collected (including the seeds).
    """

    max_depth: int
    max_fanout: int
    max_nodes: int

    @classmethod
    def create(
        cls,
        *,
        max_depth: int = 2,
        max_fanout: int = 10,
        max_nodes: int = 100,
    ) -> TraversalBudget:
        """Build a budget, validating that every bound is a positive integer.

        Args:
            max_depth: Number of hops from the seed set. Must be positive.
            max_fanout: Per-node neighbor cap per hop. Must be positive.
            max_nodes: Total node budget for the traversal. Must be positive.

        Returns:
            A frozen :class:`TraversalBudget`.

        Raises:
            ValueError: If any bound is not a positive integer.
        """
        for name, value in (
            ("max_depth", max_depth),
            ("max_fanout", max_fanout),
            ("max_nodes", max_nodes),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"TraversalBudget: {name} must be a positive int, got {value!r}")
        return cls(max_depth=max_depth, max_fanout=max_fanout, max_nodes=max_nodes)
