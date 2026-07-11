"""Tests for the :class:`RerankerBackend` protocol and a stub double."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.rerank.reranker_backend import RerankerBackend


class StubReranker:
    """A deterministic :class:`RerankerBackend` returning scripted scores."""

    def __init__(self, scores: Sequence[float]) -> None:
        self._scores = list(scores)
        self.calls: list[str] = []

    async def score(self, query: str, documents: Sequence[Mapping[str, Any]]) -> list[float]:
        self.calls.append(query)
        return list(self._scores[: len(documents)])


class NotAReranker:
    """Lacks ``score`` — must fail the runtime-checkable protocol check."""


class TestRerankerBackendProtocol(unittest.IsolatedAsyncioTestCase):
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(StubReranker([1.0]), RerankerBackend)

    def test_non_conforming_object_is_rejected(self) -> None:
        assert not isinstance(NotAReranker(), RerankerBackend)

    async def test_stub_returns_one_score_per_document(self) -> None:
        backend = StubReranker([0.1, 0.2, 0.3])
        scores = await backend.score("q", [{"text": "a"}, {"text": "b"}])
        assert scores == [0.1, 0.2]
        assert backend.calls == ["q"]


if __name__ == "__main__":
    unittest.main()
