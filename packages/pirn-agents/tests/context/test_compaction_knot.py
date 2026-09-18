"""Unit tests for :class:`CompactionKnot`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.tapestry import Tapestry

from pirn_agents.context.compaction_knot import CompactionKnot
from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.compaction_result import CompactionResult
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.summary_memory_compactor import SummaryMemoryCompactor
from pirn_agents.context.token_counter import TokenCounter
from tests.context._stubs import StubSummarizer, StubWordTokenEstimator


def _make_knot() -> CompactionKnot:
    @KnotFactory.knot
    async def _s() -> SummaryMemoryCompactor:
        return SummaryMemoryCompactor(summarizer=StubSummarizer())

    with Tapestry():
        strategy = _s(_config=KnotConfig(id="s"))
        request = _s(_config=KnotConfig(id="r"))
        return CompactionKnot(strategy=strategy, request=request, _config=KnotConfig(id="compact"))


def _request() -> CompactionRequest:
    counter = TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)
    items = (
        ContextItem(content="a a a a", position=1),
        ContextItem(content="b b b b", position=2),
        ContextItem(content="c c c c", position=3),
    )
    return CompactionRequest(items=items, budget=6, counter=counter)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_runs_strategy(self) -> None:
        k = _make_knot()
        strategy = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await k.process(strategy=strategy, request=_request())
        assert isinstance(result, CompactionResult)
        assert result.triggered is True

    async def test_rejects_non_strategy(self) -> None:
        k = _make_knot()
        result = await k({"strategy": "nope", "request": _request()})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_request(self) -> None:
        k = _make_knot()
        strategy = SummaryMemoryCompactor(summarizer=StubSummarizer())
        with self.assertRaisesRegex(TypeError, "request"):
            await k.process(strategy=strategy, request="nope")


if __name__ == "__main__":
    unittest.main()
