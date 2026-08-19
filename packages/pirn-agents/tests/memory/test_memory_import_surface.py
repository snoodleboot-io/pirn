"""Characterization test pinning the memory umbrella's public import paths.

After the umbrella consolidation these are the canonical module locations for
the memory public API. Importing every symbol here (and checking the Knot ones
are still Knots) turns any accidental future move or rename into a red test
rather than a silent break for downstream importers.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot

from pirn_agents.memory.conversation_buffer import ConversationBuffer
from pirn_agents.memory.management.entity_profile import EntityProfile
from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.management.typed_memory_validator import TypedMemoryValidator
from pirn_agents.memory.management.typed_memory_writer import TypedMemoryWriter
from pirn_agents.memory.memory_retriever import MemoryRetriever
from pirn_agents.memory.memory_writer import MemoryWriter
from pirn_agents.memory.memory_writer_base import MemoryWriterBase
from pirn_agents.memory.patterns.episodic_episode_writer import EpisodicEpisodeWriter
from pirn_agents.memory.patterns.episodic_memory_pipeline import EpisodicMemoryPipeline
from pirn_agents.memory.patterns.procedural_memory_pipeline import (
    ProceduralMemoryPipeline,
)
from pirn_agents.memory.patterns.procedural_memory_writer import ProceduralMemoryWriter
from pirn_agents.memory.patterns.semantic_fact_writer import SemanticFactWriter
from pirn_agents.memory.patterns.semantic_memory_pipeline import SemanticMemoryPipeline
from pirn_agents.memory.patterns.working_memory_pipeline import WorkingMemoryPipeline
from pirn_agents.memory.patterns.working_memory_window_writer import (
    WorkingMemoryWindowWriter,
)
from pirn_agents.memory.stores.data_store_memory_store import DataStoreMemoryStore
from pirn_agents.memory.stores.knots.memory_store_knot import MemoryStoreKnot
from pirn_agents.memory.stores.memory_store import MemoryStore

# Every symbol on the pinned public surface.
PUBLIC_SYMBOLS: tuple[object, ...] = (
    MemoryStore,
    DataStoreMemoryStore,
    MemoryStoreKnot,
    MemoryWriter,
    MemoryWriterBase,
    MemoryRetriever,
    ConversationBuffer,
    MemoryRecord,
    MemoryProvenance,
    EntityProfile,
    TypedMemoryWriter,
    TypedMemoryValidator,
    EpisodicEpisodeWriter,
    SemanticFactWriter,
    ProceduralMemoryWriter,
    WorkingMemoryWindowWriter,
    EpisodicMemoryPipeline,
    SemanticMemoryPipeline,
    ProceduralMemoryPipeline,
    WorkingMemoryPipeline,
)

# The subset that must remain Knot subclasses at their pinned paths.
KNOT_SYMBOLS: tuple[type, ...] = (
    MemoryStoreKnot,
    MemoryWriter,
    MemoryWriterBase,
    MemoryRetriever,
    ConversationBuffer,
    TypedMemoryWriter,
    TypedMemoryValidator,
    EpisodicEpisodeWriter,
    SemanticFactWriter,
    ProceduralMemoryWriter,
    WorkingMemoryWindowWriter,
    EpisodicMemoryPipeline,
    SemanticMemoryPipeline,
    ProceduralMemoryPipeline,
    WorkingMemoryPipeline,
)


class TestPublicImportSurface(unittest.TestCase):
    def test_every_pinned_symbol_resolves(self) -> None:
        # Arrange / Act / Assert
        for symbol in PUBLIC_SYMBOLS:
            with self.subTest(symbol=getattr(symbol, "__name__", symbol)):
                assert symbol is not None

    def test_knot_symbols_are_knot_subclasses(self) -> None:
        # Arrange / Act / Assert
        for symbol in KNOT_SYMBOLS:
            with self.subTest(symbol=symbol.__name__):
                assert issubclass(symbol, Knot)


if __name__ == "__main__":
    unittest.main()
