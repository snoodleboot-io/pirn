"""LSP contract tests for :class:`Writer` and its concrete writers.

These pin the substitutability guarantees behind the writer umbrella's DIP seam
(WS5 S7, PIR-728): the base is-a :class:`~pirn.core.knot.Knot` whose
:meth:`process` is abstract, every concrete writer is-a ``Writer`` (and
therefore a ``Knot``), and each concrete overrides ``process`` so it persists
state rather than raising the base ``NotImplementedError``. The memory umbrella
is the sole implementer family: its
:class:`~pirn_agents.memory.memory_writer_base.MemoryWriterBase` rebases onto
``Writer``, so all six memory writers become ``Writer`` implementations
transitively.

Per-concrete runtime round-trips live with each concrete's own suite (each
``process`` needs bespoke wiring); this module stays type/contract-focused.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.writer import Writer
from pirn_agents.memory.management.typed_memory_writer import TypedMemoryWriter
from pirn_agents.memory.memory_writer import MemoryWriter
from pirn_agents.memory.memory_writer_base import MemoryWriterBase
from pirn_agents.memory.patterns.episodic_episode_writer import EpisodicEpisodeWriter
from pirn_agents.memory.patterns.procedural_memory_writer import ProceduralMemoryWriter
from pirn_agents.memory.patterns.semantic_fact_writer import SemanticFactWriter
from pirn_agents.memory.patterns.working_memory_window_writer import (
    WorkingMemoryWindowWriter,
)

CONCRETE_WRITERS: tuple[type[Writer], ...] = (
    MemoryWriter,
    TypedMemoryWriter,
    EpisodicEpisodeWriter,
    SemanticFactWriter,
    ProceduralMemoryWriter,
    WorkingMemoryWindowWriter,
)


def _bare(cls: type[Knot]) -> Knot:
    """Build a config-only knot instance, bypassing dependency wiring.

    ``process`` takes all of its inputs as explicit keyword arguments, so a bare
    instance is sufficient to exercise the abstract-base contract without a live
    graph.
    """
    with Tapestry():
        knot = cls.__new__(cls)
        object.__setattr__(knot, "_config", KnotConfig(id="x"))
    return knot


class TestBaseIsAbstractKnot(unittest.IsolatedAsyncioTestCase):
    def test_base_is_knot_subclass(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(Writer, Knot)

    async def test_base_process_raises_not_implemented_naming_class(self) -> None:
        # Arrange
        base = _bare(Writer)
        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "Writer"):
            await base.process()


class TestConcreteSubstitutability(unittest.TestCase):
    def test_memory_writer_base_is_a_writer(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(MemoryWriterBase, Writer)

    def test_every_concrete_writer_is_a_writer(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_WRITERS:
            with self.subTest(writer=cls.__name__):
                assert issubclass(cls, Writer)
                assert issubclass(cls, Knot)

    def test_every_concrete_writer_overrides_process(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_WRITERS:
            with self.subTest(writer=cls.__name__):
                assert cls.process is not Writer.process


if __name__ == "__main__":
    unittest.main()
