"""Tests for the :class:`RerankerBackend` base class and a stub double."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.rerank.cross_encoder_reranker import CrossEncoderReranker
from pirn_agents.rerank.reranker_backend import RerankerBackend


class StubReranker(RerankerBackend):
    """A deterministic :class:`RerankerBackend` returning scripted scores."""

    def __init__(self, scores: Sequence[float]) -> None:
        self._scores = list(scores)
        self.calls: list[str] = []

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        self.calls.append(query)
        return list(self._scores[: len(documents)])


class NotAReranker:
    """Does not subclass the base — must fail the nominal ``isinstance`` check."""


class TestRerankerBackendContract(unittest.IsolatedAsyncioTestCase):
    def test_base_is_opaque_value(self) -> None:
        # Arrange / Act / Assert: stateful backend bases inherit the opaque contract.
        self.assertTrue(issubclass(RerankerBackend, PirnOpaqueValue))

    def test_cross_encoder_subclasses_base(self) -> None:
        # Arrange / Act / Assert: the concrete adapter declares the base nominally.
        self.assertTrue(issubclass(CrossEncoderReranker, RerankerBackend))

    def test_subclass_instance_is_a_backend(self) -> None:
        # Arrange / Act / Assert: explicit subclasses pass the knot's isinstance guard.
        self.assertIsInstance(StubReranker([1.0]), RerankerBackend)

    def test_non_subclass_is_rejected(self) -> None:
        # Arrange / Act / Assert: structural look-alikes no longer count.
        self.assertNotIsInstance(NotAReranker(), RerankerBackend)

    async def test_base_score_raises_not_implemented(self) -> None:
        # Arrange: a bare base instance (interface style — instantiable, no abc).
        backend = RerankerBackend()

        # Act / Assert: the abstract method reports the owning class.
        with self.assertRaisesRegex(NotImplementedError, "RerankerBackend"):
            await backend.score("q", [{"text": "a"}])

    async def test_stub_returns_one_score_per_document(self) -> None:
        backend = StubReranker([0.1, 0.2, 0.3])
        scores = await backend.score("q", [{"text": "a"}, {"text": "b"}])
        assert scores == [0.1, 0.2]
        assert backend.calls == ["q"]


if __name__ == "__main__":
    unittest.main()
