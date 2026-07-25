"""Unit tests for :class:`SummaryMemoryCompactor`."""

from __future__ import annotations

import unittest

from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.context_budget import ContextBudget
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.summary_memory_compactor import SummaryMemoryCompactor
from pirn_agents.context.token_counter import TokenCounter
from tests.context._stubs import (
    RecordingMemoryStore,
    StubSummarizer,
    StubWordTokenEstimator,
)


def _counter() -> TokenCounter:
    return TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)


def _request(items: tuple[ContextItem, ...], **kwargs: object) -> CompactionRequest:
    params: dict[str, object] = {"budget": 6, "counter": _counter()}
    params.update(kwargs)
    return CompactionRequest(items=items, **params)  # type: ignore[arg-type]


_ITEMS = (
    ContextItem(content="a a a a", position=1),
    ContextItem(content="b b b b", position=2),
    ContextItem(content="c c c c", position=3),
)


class TestTrigger(unittest.IsolatedAsyncioTestCase):
    async def test_below_threshold_is_no_op(self) -> None:
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await compactor.compact(_request(_ITEMS, budget=100))
        assert result.triggered is False
        assert result.retained == _ITEMS
        assert result.evicted == ()
        assert result.summary == ""
        assert result.summary_item is None

    async def test_above_threshold_summarizes_oldest(self) -> None:
        summarizer = StubSummarizer()
        compactor = SummaryMemoryCompactor(summarizer=summarizer)
        result = await compactor.compact(_request(_ITEMS, budget=6))
        assert result.triggered is True
        # Oldest two turns are evicted in oldest-first order.
        assert [i.content for i in result.evicted] == ["a a a a", "b b b b"]
        assert summarizer.summarize_calls == [("a a a a", "b b b b")]
        # Summary replaces the evicted block in place; newest turn survives.
        assert [i.content for i in result.retained] == ["SUMMARY[2]", "c c c c"]

    async def test_summary_item_is_pinned(self) -> None:
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await compactor.compact(_request(_ITEMS, budget=6))
        assert result.summary_item is not None
        assert result.summary_item.pinned is True
        assert result.summary_item.kind == "summary"

    async def test_reports_token_deltas(self) -> None:
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await compactor.compact(_request(_ITEMS, budget=6))
        assert result.tokens_before == 12
        # "SUMMARY[2]" (1 token) + "c c c c" (4 tokens).
        assert result.tokens_after == 5

    async def test_accepts_context_budget(self) -> None:
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        budget = ContextBudget(max_tokens=6)
        result = await compactor.compact(_request(_ITEMS, budget=budget))
        assert result.triggered is True


class TestPinnedPreservation(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_oldest_is_never_evicted(self) -> None:
        items = (
            ContextItem(content="a a a a", position=1, pinned=True),
            ContextItem(content="b b b b", position=2),
            ContextItem(content="c c c c", position=3),
        )
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await compactor.compact(_request(items, budget=6))
        contents = [i.content for i in result.retained]
        assert "a a a a" in contents
        assert all(i.content != "a a a a" for i in result.evicted)

    async def test_all_pinned_is_no_op_even_over_budget(self) -> None:
        items = (
            ContextItem(content="a a a a", position=1, pinned=True),
            ContextItem(content="b b b b", position=2, pinned=True),
        )
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        result = await compactor.compact(_request(items, budget=2))
        assert result.triggered is False
        assert result.retained == items


class TestMemoryIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_persists_summary_when_key_and_store_present(self) -> None:
        store = RecordingMemoryStore()
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer(), memory_store=store)
        await compactor.compact(_request(_ITEMS, budget=6, persist_key="conv-1"))
        assert len(store.stored) == 1
        key, value = store.stored[0]
        assert key == "conv-1"
        assert value["summary"] == "SUMMARY[2]"
        assert value["evicted_count"] == 2

    async def test_no_persist_without_key(self) -> None:
        store = RecordingMemoryStore()
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer(), memory_store=store)
        await compactor.compact(_request(_ITEMS, budget=6))
        assert store.stored == []

    async def test_no_persist_when_not_triggered(self) -> None:
        store = RecordingMemoryStore()
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer(), memory_store=store)
        await compactor.compact(_request(_ITEMS, budget=100, persist_key="conv-1"))
        assert store.stored == []


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_constructor_rejects_non_summarizer(self) -> None:
        with self.assertRaisesRegex(TypeError, "summarizer"):
            SummaryMemoryCompactor(summarizer=object())  # type: ignore[arg-type]

    async def test_constructor_rejects_bad_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "memory_store"):
            SummaryMemoryCompactor(summarizer=StubSummarizer(), memory_store=object())  # type: ignore[arg-type]

    async def test_compact_rejects_non_request(self) -> None:
        compactor = SummaryMemoryCompactor(summarizer=StubSummarizer())
        with self.assertRaisesRegex(TypeError, "request"):
            await compactor.compact("nope")  # type: ignore[arg-type]


class TestRequestValidation(unittest.TestCase):
    def test_rejects_bad_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "fill_threshold"):
            CompactionRequest(items=_ITEMS, budget=6, counter=_counter(), fill_threshold=1.5)

    def test_rejects_non_tuple_items(self) -> None:
        with self.assertRaisesRegex(TypeError, "items"):
            CompactionRequest(items=[_ITEMS[0]], budget=6, counter=_counter())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
