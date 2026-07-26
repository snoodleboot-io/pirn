"""Vending knots for the vector-store domain.

Nests the vector-store :class:`~pirn.core.knot.Knot` adapters under their domain
(mirroring core's ``connectors/knots/`` layout). Ships
:class:`~pirn_agents.retrieval.vector_stores.knots.vector_store_knot.VectorStoreKnot`,
the pass-through knot that vends a pooled vector-store connector through the
graph. Importing this subpackage pulls in no backend.
"""

from __future__ import annotations
