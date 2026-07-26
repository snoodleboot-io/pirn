"""``Retriever`` — shared interface for every retrieval knot.

The DIP seam behind the retriever family. A retriever takes a query (plus a
store/index and optional shaping config) and returns ranked candidate hits.
Across the package this shape is implemented by the RAG retrievers
(``specializations/rag/*`` and its ``indexing/`` variants), the memory-facing
retrievers (:class:`~pirn_agents.memory.memory_retriever.MemoryRetriever`,
``EpisodicMemoryRetriever``), and — via
:class:`~pirn_agents.retrieval.hybrid_retriever_base.HybridRetrieverBase` — the
two RRF hybrid retrievers. Consolidating them onto one base lets callers depend
on the abstraction ``Retriever`` rather than each concrete, and gives every
concrete a single substitutable contract.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.core.knot.Knot` whose :meth:`process` raises
:class:`NotImplementedError`; each concrete retriever overrides ``process`` with
its own keyword signature — exactly as it previously overrode ``Knot.process`` —
so the rebase changes no observable behavior.

References:
    - :class:`pirn.core.knot.Knot`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class Retriever(Knot):
    """Abstract base for knots that retrieve ranked candidates for a query.

    Concrete retrievers subclass this and override :meth:`process` with their own
    keyword parameters and return type. The base itself is never placed in a
    graph directly; it exists so retrievers share one abstraction (DIP) and one
    substitutable contract (LSP): each ``process`` resolves a query against some
    store or index and returns its ranked hits.
    """

    async def process(self, **kwargs: Any) -> Any:
        """Retrieve ranked candidates for a query.

        Concrete subclasses override this with their own keyword parameters and
        return type. The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")
