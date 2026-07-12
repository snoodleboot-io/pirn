"""Unit tests for :class:`ContextAssembler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.context.assembled_context import AssembledContext
from pirn_agents.context.context_assembler import ContextAssembler
from pirn_agents.context.context_budget import ContextBudget
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.importance_eviction_policy import ImportanceEvictionPolicy
from pirn_agents.context.recency_eviction_policy import RecencyEvictionPolicy
from pirn_agents.context.relevance_eviction_policy import RelevanceEvictionPolicy
from pirn_agents.context.token_counter import TokenCounter
from tests.context._stubs import StubWordTokenEstimator


def _counter() -> TokenCounter:
    # One token per whitespace word, no per-message overhead: token cost of an
    # item equals its word count, so budgets are easy to reason about.
    return TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=0)


def _make_knot() -> ContextAssembler:
    @knot
    async def _items() -> tuple:
        return ()

    @knot
    async def _counter_knot() -> TokenCounter:
        return _counter()

    with Tapestry():
        items = _items(_config=KnotConfig(id="items"))
        counter = _counter_knot(_config=KnotConfig(id="counter"))
        return ContextAssembler(
            items=items,
            budget=100,
            counter=counter,
            _config=KnotConfig(id="assemble"),
        )


def _word_item(content: str, **kwargs: object) -> ContextItem:
    return ContextItem(content=content, **kwargs)  # type: ignore[arg-type]


class TestBudgetFitting(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_all_when_under_budget(self) -> None:
        k = _make_knot()
        items = (_word_item("one two"), _word_item("three"))
        result = await k.process(items=items, budget=10, counter=_counter())
        assert isinstance(result, AssembledContext)
        assert result.kept == items
        assert result.evicted == ()
        assert result.total_tokens == 3

    async def test_evicts_until_within_budget(self) -> None:
        k = _make_knot()
        # each item is 2 tokens; budget 4 -> keep 2, drop 1.
        items = (
            _word_item("a a", position=1),
            _word_item("b b", position=2),
            _word_item("c c", position=3),
        )
        result = await k.process(
            items=items, budget=4, counter=_counter(), policy=RecencyEvictionPolicy()
        )
        assert result.total_tokens == 4
        # recency drops the oldest (position 1) first.
        assert [i.content for i in result.evicted] == ["a a"]
        assert [i.content for i in result.kept] == ["b b", "c c"]

    async def test_kept_preserves_original_order(self) -> None:
        k = _make_knot()
        items = (
            _word_item("a a", position=3),
            _word_item("b b", position=1),
            _word_item("c c", position=2),
        )
        result = await k.process(
            items=items, budget=4, counter=_counter(), policy=RecencyEvictionPolicy()
        )
        # position-1 item ("b b") is evicted; remaining keep input order.
        assert [i.content for i in result.kept] == ["a a", "c c"]

    async def test_accepts_context_budget_with_reserved(self) -> None:
        k = _make_knot()
        items = (_word_item("a a"), _word_item("b b"))
        budget = ContextBudget(max_tokens=6, reserved_tokens=3)  # available == 3
        result = await k.process(items=items, budget=budget, counter=_counter())
        assert result.total_tokens <= 3
        assert len(result.evicted) == 1

    async def test_zero_budget_evicts_all_unpinned(self) -> None:
        k = _make_knot()
        items = (_word_item("a"), _word_item("b"))
        result = await k.process(items=items, budget=0, counter=_counter())
        assert result.kept == ()
        assert len(result.evicted) == 2
        assert result.total_tokens == 0


class TestPinned(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_items_are_never_evicted(self) -> None:
        k = _make_knot()
        items = (
            _word_item("pinned words here", position=1, pinned=True),
            _word_item("b b", position=2),
            _word_item("c c", position=3),
        )
        result = await k.process(
            items=items, budget=3, counter=_counter(), policy=RecencyEvictionPolicy()
        )
        kept_contents = [i.content for i in result.kept]
        assert "pinned words here" in kept_contents

    async def test_pinned_can_exceed_budget(self) -> None:
        k = _make_knot()
        items = (_word_item("one two three four five", pinned=True),)
        result = await k.process(items=items, budget=2, counter=_counter())
        # Pinned content is retained even though it exceeds the budget.
        assert result.kept == items
        assert result.total_tokens == 5


class TestPolicySelection(unittest.IsolatedAsyncioTestCase):
    async def test_relevance_policy_drops_least_relevant(self) -> None:
        k = _make_knot()
        items = (
            _word_item("a a", relevance=0.1),
            _word_item("b b", relevance=0.9),
            _word_item("c c", relevance=0.5),
        )
        result = await k.process(
            items=items, budget=4, counter=_counter(), policy=RelevanceEvictionPolicy()
        )
        assert [i.content for i in result.evicted] == ["a a"]

    async def test_importance_policy_drops_least_important(self) -> None:
        k = _make_knot()
        items = (
            _word_item("a a", priority=5),
            _word_item("b b", priority=1),
            _word_item("c c", priority=9),
        )
        result = await k.process(
            items=items, budget=4, counter=_counter(), policy=ImportanceEvictionPolicy()
        )
        assert [i.content for i in result.evicted] == ["b b"]

    async def test_defaults_to_recency_when_policy_omitted(self) -> None:
        k = _make_knot()
        items = (
            _word_item("a a", position=1),
            _word_item("b b", position=2),
        )
        result = await k.process(items=items, budget=2, counter=_counter())
        assert [i.content for i in result.evicted] == ["a a"]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_items(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "items"):
            await k.process(items=5, budget=1, counter=_counter())  # type: ignore[arg-type]

    async def test_rejects_non_item_element(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, r"items\[0\]"):
            await k.process(items=("x",), budget=1, counter=_counter())  # type: ignore[arg-type]

    async def test_rejects_non_counter(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "counter"):
            await k.process(items=(), budget=1, counter="nope")  # type: ignore[arg-type]

    async def test_rejects_bad_budget_type(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "budget"):
            await k.process(items=(), budget="big", counter=_counter())  # type: ignore[arg-type]

    async def test_rejects_negative_budget(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "non-negative"):
            await k.process(items=(), budget=-1, counter=_counter())

    async def test_rejects_non_policy(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "policy"):
            await k.process(items=(), budget=1, counter=_counter(), policy="nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
