"""Tests for :class:`QueryRouteClassifier`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.query_route_classifier import QueryRouteClassifier
from tests.specializations.conftest import StubLLMProvider


def _classifier() -> QueryRouteClassifier:
    with Tapestry():
        knot = QueryRouteClassifier.__new__(QueryRouteClassifier)
        object.__setattr__(knot, "_config", KnotConfig(id="classify"))
    return knot


class TestQueryRouteClassifier(unittest.IsolatedAsyncioTestCase):
    async def test_exact_match(self) -> None:
        knot = _classifier()
        chosen = await knot.process(
            query="q", llm=StubLLMProvider(["code"]), route_names=["docs", "code"]
        )
        assert chosen == "code"

    async def test_substring_match(self) -> None:
        knot = _classifier()
        chosen = await knot.process(
            query="q",
            llm=StubLLMProvider(["I would use the docs index"]),
            route_names=["docs", "code"],
        )
        assert chosen == "docs"

    async def test_unrecognised_falls_back_to_first(self) -> None:
        knot = _classifier()
        chosen = await knot.process(
            query="q", llm=StubLLMProvider(["banana"]), route_names=["docs", "code"]
        )
        assert chosen == "docs"

    async def test_rejects_empty_routes(self) -> None:
        knot = _classifier()
        with self.assertRaisesRegex(ValueError, "route_names must be non-empty"):
            await knot.process(query="q", llm=StubLLMProvider(["x"]), route_names=[])
