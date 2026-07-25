"""Chunking-strategy library (F25-S2 / PIR-575).

The shared home for chunking across the codebase: a set of named, pluggable
strategies behind the
:class:`~pirn_agents.specializations.document_processing.chunking.chunking_strategy.ChunkingStrategy`
interface, each emitting
:class:`~pirn_agents.specializations.document_processing.chunking.chunk.Chunk`
objects. F9 indexing patterns reuse these strategies rather than duplicating
splitting logic. Every strategy is provider-neutral; only the semantic strategy
takes an injected embedding provider, and it uses numpy (already in the core
closure) for its vector math — no optional backend is imported here.
"""

from __future__ import annotations
