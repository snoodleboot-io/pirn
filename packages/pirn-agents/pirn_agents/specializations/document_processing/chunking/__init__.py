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

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.code_aware_chunking_strategy import (
    CodeAwareChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.parent_child_chunking_strategy import (
    ParentChildChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.recursive_character_chunking_strategy import (
    RecursiveCharacterChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.semantic_chunking_strategy import (
    SemanticChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.sentence_window_chunking_strategy import (
    SentenceWindowChunkingStrategy,
)

__all__: list[str] = [
    "Chunk",
    "ChunkingStrategy",
    "CodeAwareChunkingStrategy",
    "FixedSizeChunkingStrategy",
    "ParentChildChunkingStrategy",
    "RecursiveCharacterChunkingStrategy",
    "SemanticChunkingStrategy",
    "SentenceWindowChunkingStrategy",
]
