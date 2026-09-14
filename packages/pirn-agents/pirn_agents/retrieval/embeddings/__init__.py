"""Concrete :class:`~pirn_agents.retrieval.embeddings.embedding_provider.EmbeddingProvider` implementations.

This subpackage ships the batching base provider plus provider-neutral
adapters (an HTTP/OpenAI-compatible adapter and a local sentence-transformer
adapter). Importing it pulls in no backend: every optional dependency is lazily
imported at the point of use via :meth:`~pirn.core.optional_dependency.OptionalDependency.require`.
"""

from __future__ import annotations
