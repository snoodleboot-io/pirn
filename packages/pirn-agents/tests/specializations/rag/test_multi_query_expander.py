"""Tests for :class:`MultiQueryExpander`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.multi_query_expander import MultiQueryExpander
from tests.specializations.conftest import StubLLMProvider


def _expander() -> MultiQueryExpander:
    with Tapestry():
        knot = MultiQueryExpander.__new__(MultiQueryExpander)
        object.__setattr__(knot, "_config", KnotConfig(id="expand"))
    return knot


class TestMultiQueryExpander(unittest.IsolatedAsyncioTestCase):
    async def test_expands_and_keeps_original_first(self) -> None:
        llm = StubLLMProvider(["phrasing two\nphrasing three\nphrasing four"])
        knot = _expander()
        variants = await knot.process(query="original", llm=llm, num_queries=4)
        assert variants == ["original", "phrasing two", "phrasing three", "phrasing four"]

    async def test_num_queries_one_skips_llm(self) -> None:
        llm = StubLLMProvider(["should-not-be-used"])
        knot = _expander()
        variants = await knot.process(query="solo", llm=llm, num_queries=1)
        assert variants == ["solo"]
        assert llm.calls == []

    async def test_deduplicates_and_caps(self) -> None:
        llm = StubLLMProvider(["original\ndup\ndup\nextra"])
        knot = _expander()
        variants = await knot.process(query="original", llm=llm, num_queries=3)
        assert variants == ["original", "dup", "extra"]

    async def test_rejects_non_string_query(self) -> None:
        knot = _expander()
        with self.assertRaisesRegex(TypeError, "query must be a string"):
            await knot.process(query=1, llm=StubLLMProvider(["x"]), num_queries=2)  # type: ignore[arg-type]

    async def test_rejects_non_positive_num_queries(self) -> None:
        knot = _expander()
        with self.assertRaisesRegex(ValueError, "num_queries must be a positive int"):
            await knot.process(query="q", llm=StubLLMProvider(["x"]), num_queries=0)
