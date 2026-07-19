"""Concrete :class:`~pirn_agents.embedding_provider.EmbeddingProvider` implementations.

This subpackage ships the batching base provider plus provider-neutral
adapters (an HTTP/OpenAI-compatible adapter and a local sentence-transformer
adapter). Importing it pulls in no backend: every optional dependency is lazily
imported at the point of use via :func:`pirn_agents._require._require`.
"""

from __future__ import annotations
