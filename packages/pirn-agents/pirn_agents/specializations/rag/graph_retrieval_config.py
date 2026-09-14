"""``GraphRetrievalConfig`` — retrieval breadth for graph-shaped RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class GraphRetrievalConfig(PirnOpaqueValue):
    """How many entity/relation hits a graph-RAG fetch pulls before flattening.

    Graph retrieval is deliberately *wider* than flat vector retrieval: hits are
    entities and relations that a sub-graph builder then collapses into a single
    context block, so the useful breadth is an order of magnitude above the
    top-k of a passage search. Keeping that number here — rather than as a bare
    literal on the pipeline — states the reason once and gives the knob a name.

    Attributes
    ----------
    top_k:
        Maximum entity/relation hits fetched per query. Must be >= 1. Defaults
        to 25, the pipeline's historical breadth.
    """

    top_k: int = 25

    def __post_init__(self) -> None:
        """Validate the retrieval breadth.

        Raises:
            ValueError: If ``top_k`` is not an int >= 1.
        """
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or self.top_k < 1:
            raise ValueError(f"GraphRetrievalConfig: top_k must be an int >= 1, got {self.top_k!r}")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"top_k": self.top_k}
