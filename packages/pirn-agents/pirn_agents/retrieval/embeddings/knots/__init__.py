"""Vending knots for the embeddings domain.

Nests the embedding :class:`~pirn.core.knot.Knot` adapters under their domain
(mirroring core's ``connectors/knots/`` layout). Ships
:class:`~pirn_agents.retrieval.embeddings.knots.embedding_provider_knot.EmbeddingProviderKnot`,
the pass-through knot that vends an
:class:`~pirn_agents.retrieval.embeddings.embedding_provider.EmbeddingProvider`
through the graph. Importing this subpackage pulls in no backend.
"""

from __future__ import annotations
