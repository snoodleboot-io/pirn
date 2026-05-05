"""Unit tests for :class:`_MapReduceSummariser`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._map_reduce_summariser import (
    _MapReduceSummariser,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestMapReduceSummariserProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_empty_string(self) -> None:
        llm = StubLLMProvider([])
        with Tapestry() as t:
            _MapReduceSummariser(
                chunks=[],
                llm=llm,
                _config=KnotConfig(id="mrs"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mrs"] == ""

    async def test_single_chunk_returns_direct_summary(self) -> None:
        llm = StubLLMProvider(["short summary"])
        with Tapestry() as t:
            _MapReduceSummariser(
                chunks=["long text here"],
                llm=llm,
                _config=KnotConfig(id="mrs"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mrs"] == "short summary"
        assert len(llm.calls) == 1  # no reduce step for single chunk

    async def test_multiple_chunks_triggers_reduce(self) -> None:
        llm = StubLLMProvider(["sum1", "sum2", "final"])
        with Tapestry() as t:
            _MapReduceSummariser(
                chunks=["a", "b"],
                llm=llm,
                _config=KnotConfig(id="mrs"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mrs"] == "final"
        assert len(llm.calls) == 3  # 2 map + 1 reduce
