"""Tests for :class:`RoutedRetriever`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.route_table import RouteTable
from pirn_agents.specializations.rag.routed_retriever import RoutedRetriever
from tests.specializations.conftest import StubMemoryStore


def _retriever() -> RoutedRetriever:
    with Tapestry():
        knot = RoutedRetriever.__new__(RoutedRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="route"))
    return knot


class TestRoutedRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_retrieves_from_selected_store(self) -> None:
        docs = StubMemoryStore([{"id": "d1", "text": "doc hit"}])
        code = StubMemoryStore([{"id": "c1", "text": "code hit"}])
        table = RouteTable({"docs": docs, "code": code})
        knot = _retriever()
        results = await knot.process(route="code", routes=table, query="q", top_k=5)
        assert [r["id"] for r in results] == ["c1"]
        assert results[0]["route"] == "code"
        assert code.search_queries == ["q"]
        assert docs.search_queries == []

    async def test_unknown_route_falls_back_to_first(self) -> None:
        docs = StubMemoryStore([{"id": "d1"}])
        table = RouteTable({"docs": docs})
        knot = _retriever()
        results = await knot.process(route="missing", routes=table, query="q", top_k=5)
        assert results[0]["route"] == "docs"

    async def test_rejects_non_route_table(self) -> None:
        knot = _retriever()
        with self.assertRaisesRegex(TypeError, "routes must be a RouteTable"):
            await knot.process(route="x", routes="nope", query="q", top_k=5)  # type: ignore[arg-type]
