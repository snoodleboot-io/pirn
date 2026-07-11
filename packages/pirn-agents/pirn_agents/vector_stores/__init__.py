"""Concrete :class:`pirn_agents.memory_store.MemoryStore` vector-store adapters.

Ships the vector-native record/match value types, an abstract
:class:`~pirn_agents.vector_stores.vector_memory_store.VectorMemoryStore` that
layers the keyed ``MemoryStore`` surface over a vector upsert/query/delete core,
and concrete stores: a zero-dependency numpy in-memory reference plus lazy
pgvector, Qdrant, and Chroma adapters. Importing this subpackage pulls in no
external backend.
"""

from __future__ import annotations
