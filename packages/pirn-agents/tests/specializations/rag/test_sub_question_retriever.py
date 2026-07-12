"""Tests for :class:`SubQuestionRetriever`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.sub_question_retriever import SubQuestionRetriever
from tests.specializations.conftest import StubMemoryStore


class _PerQueryStore(MemoryStore):
    def __init__(self, mapping: Mapping[str, list[Mapping[str, Any]]]) -> None:
        self._mapping = {k: [dict(h) for h in v] for k, v in mapping.items()}
        self.search_queries: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        self.search_queries.append(query)
        hits = self._mapping.get(query, [])

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for hit in hits[:top_k]:
                yield hit

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


def _retriever() -> SubQuestionRetriever:
    with Tapestry():
        knot = SubQuestionRetriever.__new__(SubQuestionRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="retrieve"))
    return knot


class TestSubQuestionRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_unions_and_dedupes(self) -> None:
        store = _PerQueryStore(
            {
                "q1": [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}],
                "q2": [{"id": "2", "text": "b"}, {"id": "3", "text": "c"}],
            }
        )
        knot = _retriever()
        docs = await knot.process(sub_questions=["q1", "q2"], store=store, top_k=5)
        ids = sorted(d["id"] for d in docs)
        assert ids == ["1", "2", "3"]
        assert sorted(store.search_queries) == ["q1", "q2"]

    async def test_records_sub_question_provenance(self) -> None:
        store = _PerQueryStore({"only": [{"id": "1", "text": "a"}]})
        knot = _retriever()
        docs = await knot.process(sub_questions=["only"], store=store, top_k=5)
        assert docs[0]["sub_question"] == "only"

    async def test_empty_sub_questions(self) -> None:
        knot = _retriever()
        docs = await knot.process(sub_questions=[], store=StubMemoryStore([]), top_k=5)
        assert docs == []

    async def test_rejects_non_positive_top_k(self) -> None:
        knot = _retriever()
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await knot.process(sub_questions=["q"], store=StubMemoryStore([]), top_k=0)
