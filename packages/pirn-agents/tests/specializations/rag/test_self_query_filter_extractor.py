"""Tests for :class:`SelfQueryFilterExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.self_query_filter_extractor import SelfQueryFilterExtractor
from tests.specializations.conftest import StubLLMProvider


def _extractor() -> SelfQueryFilterExtractor:
    with Tapestry():
        knot = SelfQueryFilterExtractor.__new__(SelfQueryFilterExtractor)
        object.__setattr__(knot, "_config", KnotConfig(id="extract"))
    return knot


class TestSelfQueryFilterExtractor(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_semantic_query_and_filter(self) -> None:
        llm = StubLLMProvider(['{"query": "diffusion models", "filter": {"author": "Ho"}}'])
        knot = _extractor()
        spec = await knot.process(
            query="papers about diffusion models by Ho",
            llm=llm,
            filterable_fields=["author", "year"],
        )
        assert spec["query"] == "diffusion models"
        assert spec["metadata_filter"] == {"author": "Ho"}

    async def test_drops_non_whitelisted_fields(self) -> None:
        llm = StubLLMProvider(['{"query": "x", "filter": {"author": "Ho", "secret": "z"}}'])
        knot = _extractor()
        spec = await knot.process(query="q", llm=llm, filterable_fields=["author"])
        assert spec["metadata_filter"] == {"author": "Ho"}

    async def test_malformed_json_degrades_to_unfiltered(self) -> None:
        llm = StubLLMProvider(["not json at all"])
        knot = _extractor()
        spec = await knot.process(query="original", llm=llm, filterable_fields=["author"])
        assert spec["query"] == "original"
        assert spec["metadata_filter"] == {}

    async def test_rejects_non_string_query(self) -> None:
        knot = _extractor()
        with self.assertRaisesRegex(TypeError, "query must be a string"):
            await knot.process(query=1, llm=StubLLMProvider(["{}"]), filterable_fields=[])  # type: ignore[arg-type]
