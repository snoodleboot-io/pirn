"""Unit tests for :class:`_SummaryReducer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._summary_reducer import (
    _SummaryReducer,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> _SummaryReducer:
    with Tapestry():
        return _SummaryReducer(summaries=[], llm=llm, _config=KnotConfig(id="summarise"))


class TestSummaryReducerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_no_summaries_returns_empty_string(self) -> None:
        llm = StubLLMProvider([])
        assert await _make_knot(llm).process(summaries=[], llm=llm) == ""
        assert llm.calls == []

    async def test_single_summary_passes_through_without_a_reduce_call(self) -> None:
        llm = StubLLMProvider([])
        result = await _make_knot(llm).process(summaries=["short summary"], llm=llm)
        assert result == "short summary"
        assert len(llm.calls) == 0

    async def test_multiple_summaries_trigger_one_reduce_call(self) -> None:
        llm = StubLLMProvider(["final"])
        result = await _make_knot(llm).process(summaries=["sum1", "sum2"], llm=llm)
        assert result == "final"
        assert len(llm.calls) == 1

    async def test_reduce_user_message_numbers_the_summaries(self) -> None:
        llm = StubLLMProvider(["final"])
        await _make_knot(llm).process(summaries=["a", "b"], llm=llm)
        assert llm.calls[0][1]["content"] == "Summary 1: a\n\nSummary 2: b"
