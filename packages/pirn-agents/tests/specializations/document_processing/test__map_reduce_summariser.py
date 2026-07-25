"""Unit tests for :class:`_MapReduceSummariser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._map_reduce_summariser import (
    _MapReduceSummariser,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> _MapReduceSummariser:
    with Tapestry():
        return _MapReduceSummariser(
            chunks=[],
            llm=llm,
            _config=KnotConfig(id="mrs"),
        )


class TestMapReduceSummariserProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_empty_string(self) -> None:
        llm = StubLLMProvider([])
        k = _make_knot(llm)
        result = await k.process(chunks=[], llm=llm)
        assert result == ""

    async def test_single_chunk_returns_direct_summary(self) -> None:
        llm = StubLLMProvider(["short summary"])
        k = _make_knot(llm)
        result = await k.process(chunks=["long text here"], llm=llm)
        assert result == "short summary"
        assert len(llm.calls) == 1  # no reduce step for single chunk

    async def test_multiple_chunks_triggers_reduce(self) -> None:
        llm = StubLLMProvider(["sum1", "sum2", "final"])
        k = _make_knot(llm)
        result = await k.process(chunks=["a", "b"], llm=llm)
        assert result == "final"
        assert len(llm.calls) == 3  # 2 map + 1 reduce
