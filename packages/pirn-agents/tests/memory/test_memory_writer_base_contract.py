"""LSP contract tests for :class:`MemoryWriterBase` and its concrete writers.

These pin the substitutability guarantees behind the memory umbrella's DIP
seam: the base is-a :class:`~pirn.core.knot.Knot` whose :meth:`process` is
abstract, every concrete writer is-a ``MemoryWriterBase`` (and therefore a
``Knot``), and each concrete writer overrides ``process`` so a live instance
persists into a ``MemoryStore`` and returns the documented storage handle
rather than raising the base ``NotImplementedError``.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.management.typed_memory_writer import TypedMemoryWriter
from pirn_agents.memory.memory_writer import MemoryWriter
from pirn_agents.memory.memory_writer_base import MemoryWriterBase
from pirn_agents.memory.patterns.episodic_episode_writer import EpisodicEpisodeWriter
from pirn_agents.memory.patterns.procedural_memory_writer import ProceduralMemoryWriter
from pirn_agents.memory.patterns.semantic_fact_writer import SemanticFactWriter
from pirn_agents.memory.patterns.working_memory_window_writer import (
    WorkingMemoryWindowWriter,
)
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.conftest import StubMemoryStore
from tests.memory_management.conftest import make_record

CONCRETE_WRITERS: tuple[type[MemoryWriterBase], ...] = (
    MemoryWriter,
    TypedMemoryWriter,
    EpisodicEpisodeWriter,
    SemanticFactWriter,
    ProceduralMemoryWriter,
    WorkingMemoryWindowWriter,
)


def _bare(cls: type[Knot]) -> Knot:
    """Build a config-only knot instance, bypassing dependency wiring.

    Mirrors ``tests/test_memory_store_knot.py``: ``process`` takes all of its
    inputs as explicit keyword arguments, so a bare instance is sufficient to
    exercise the runtime contract without a live graph.
    """
    with Tapestry():
        knot = cls.__new__(cls)
        object.__setattr__(knot, "_config", KnotConfig(id="x"))
    return knot


class TestBaseIsAbstractKnot(unittest.IsolatedAsyncioTestCase):
    def test_base_is_knot_subclass(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(MemoryWriterBase, Knot)

    async def test_base_process_raises_not_implemented_naming_class(self) -> None:
        # Arrange
        base = _bare(MemoryWriterBase)
        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "MemoryWriterBase"):
            await base.process()


class TestConcreteSubstitutability(unittest.TestCase):
    def test_every_concrete_writer_is_a_memory_writer_base(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_WRITERS:
            with self.subTest(writer=cls.__name__):
                assert issubclass(cls, MemoryWriterBase)
                assert issubclass(cls, Knot)

    def test_every_concrete_writer_overrides_process(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_WRITERS:
            with self.subTest(writer=cls.__name__):
                assert cls.process is not MemoryWriterBase.process


class TestConcreteRoundTrips(unittest.IsolatedAsyncioTestCase):
    async def test_memory_writer_persists_and_returns_key(self) -> None:
        # Arrange
        writer = _bare(MemoryWriter)
        store = StubMemoryStore()
        # Act
        key = await writer.process(key="alpha", value={"v": 1}, store=store)
        # Assert
        assert key == "alpha"
        assert await store.retrieve("alpha") == {"v": 1}

    async def test_typed_memory_writer_persists_under_record_id(self) -> None:
        # Arrange
        writer = _bare(TypedMemoryWriter)
        store = StubMemoryStore()
        record = make_record(id="rec-1", content="fact")
        # Act
        key = await writer.process(record=record, store=store)
        # Assert
        assert key == "rec-1"
        assert await store.retrieve("rec-1") is not None

    async def test_episodic_episode_writer_persists_and_returns_episode_key(self) -> None:
        # Arrange
        writer = _bare(EpisodicEpisodeWriter)
        store = StubMemoryStore()
        messages = [AgentMessage(role="user", content="hello")]
        # Act
        key = await writer.process(messages=messages, session_id="sess-1", store=store)
        # Assert
        assert key.startswith("episode:")
        assert "sess-1" in key
        assert await store.retrieve(key) is not None

    async def test_semantic_fact_writer_persists_and_returns_count(self) -> None:
        # Arrange
        writer = _bare(SemanticFactWriter)
        store = StubMemoryStore()
        # Act
        count = await writer.process(facts=["the sky is blue", "water is wet"], store=store)
        # Assert
        assert count == 2

    async def test_procedural_memory_writer_persists_and_returns_procedure_key(self) -> None:
        # Arrange
        writer = _bare(ProceduralMemoryWriter)
        store = StubMemoryStore()
        response = AgentResponse(content="step 1, step 2", finish_reason="stop")
        # Act
        key = await writer.process(
            agent_response=response,
            task_description="deploy the app",
            store=store,
        )
        # Assert
        assert key.startswith("procedure:")
        assert await store.retrieve(key) is not None

    async def test_working_memory_window_writer_persists_and_returns_window(self) -> None:
        # Arrange
        writer = _bare(WorkingMemoryWindowWriter)
        store = StubMemoryStore()
        message = AgentMessage(role="user", content="first")
        # Act
        window = await writer.process(
            new_message=message,
            session_id="sess-1",
            store=store,
            max_size=5,
        )
        # Assert
        assert isinstance(window, tuple)
        assert len(window) == 1
        assert window[0].content == "first"


if __name__ == "__main__":
    unittest.main()
