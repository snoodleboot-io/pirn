"""LSP contract tests for :class:`Retriever` and its concrete retrievers.

These pin the substitutability guarantees behind the retrieval umbrella's DIP
seam (WS5 S7, PIR-728): the base is-a :class:`~pirn.core.knot.Knot` whose
:meth:`process` is abstract, every concrete retriever is-a ``Retriever`` (and
therefore a ``Knot``), and each concrete overrides ``process`` so it resolves a
query rather than raising the base ``NotImplementedError``. Twelve concretes
subclass ``Retriever`` directly; the two RRF hybrids reach it transitively
through :class:`~pirn_agents.retrieval.hybrid_retriever_base.HybridRetrieverBase`.

Per-concrete runtime round-trips live with each concrete's own suite (each
``process`` needs bespoke wiring); this module stays type/contract-focused.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.memory_retriever import MemoryRetriever
from pirn_agents.memory.patterns.episodic_memory_retriever import (
    EpisodicMemoryRetriever,
)
from pirn_agents.retrieval.graph_rag.hybrid_graph_retriever import HybridGraphRetriever
from pirn_agents.retrieval.hybrid_retriever import HybridRetriever
from pirn_agents.retrieval.hybrid_retriever_base import HybridRetrieverBase
from pirn_agents.specializations.rag.fusion_retriever import FusionRetriever
from pirn_agents.specializations.rag.indexing.auto_merging_retriever import (
    AutoMergingRetriever,
)
from pirn_agents.specializations.rag.indexing.parent_document_retriever import (
    ParentDocumentRetriever,
)
from pirn_agents.specializations.rag.indexing.raptor_retriever import RaptorRetriever
from pirn_agents.specializations.rag.indexing.sentence_window_retriever import (
    SentenceWindowRetriever,
)
from pirn_agents.specializations.rag.iterative_retriever import IterativeRetriever
from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn_agents.specializations.rag.routed_retriever import RoutedRetriever
from pirn_agents.specializations.rag.self_query_retriever import SelfQueryRetriever
from pirn_agents.specializations.rag.sub_question_retriever import SubQuestionRetriever

CONCRETE_RETRIEVERS: tuple[type[Retriever], ...] = (
    RoutedRetriever,
    MemorySearchRetriever,
    ParentDocumentRetriever,
    FusionRetriever,
    IterativeRetriever,
    RaptorRetriever,
    SelfQueryRetriever,
    SubQuestionRetriever,
    AutoMergingRetriever,
    SentenceWindowRetriever,
    EpisodicMemoryRetriever,
    MemoryRetriever,
    HybridRetriever,
    HybridGraphRetriever,
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
        assert issubclass(Retriever, Knot)

    async def test_base_process_raises_not_implemented_naming_class(self) -> None:
        # Arrange
        base = _bare(Retriever)
        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "Retriever"):
            await base.process()


class TestConcreteSubstitutability(unittest.TestCase):
    def test_every_concrete_retriever_is_a_retriever(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_RETRIEVERS:
            with self.subTest(retriever=cls.__name__):
                assert issubclass(cls, Retriever)
                assert issubclass(cls, Knot)

    def test_every_concrete_retriever_overrides_process(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_RETRIEVERS:
            with self.subTest(retriever=cls.__name__):
                assert cls.process is not Retriever.process


class TestHybridBaseReparent(unittest.TestCase):
    def test_hybrid_retriever_base_is_a_retriever(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(HybridRetrieverBase, Retriever)

    def test_hybrid_concretes_reach_retriever_transitively(self) -> None:
        # Arrange / Act / Assert
        for cls in (HybridRetriever, HybridGraphRetriever):
            with self.subTest(retriever=cls.__name__):
                assert issubclass(cls, HybridRetrieverBase)
                assert issubclass(cls, Retriever)


if __name__ == "__main__":
    unittest.main()
