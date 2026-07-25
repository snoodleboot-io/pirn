"""Unit tests for the pluggable eviction policies (each in isolation)."""

from __future__ import annotations

import unittest

from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.importance_eviction_policy import ImportanceEvictionPolicy
from pirn_agents.context.recency_eviction_policy import RecencyEvictionPolicy
from pirn_agents.context.relevance_eviction_policy import RelevanceEvictionPolicy


class TestRecency(unittest.TestCase):
    def test_orders_oldest_first(self) -> None:
        old = ContextItem(content="old", position=1)
        mid = ContextItem(content="mid", position=2)
        new = ContextItem(content="new", position=3)
        order = RecencyEvictionPolicy().order_for_eviction((new, old, mid))
        assert [item.content for item in order] == ["old", "mid", "new"]

    def test_rank_is_position(self) -> None:
        assert RecencyEvictionPolicy().eviction_rank(ContextItem(content="x", position=7)) == 7.0

    def test_rejects_non_item(self) -> None:
        with self.assertRaisesRegex(TypeError, "ContextItem"):
            RecencyEvictionPolicy().eviction_rank("nope")  # type: ignore[arg-type]


class TestRelevance(unittest.TestCase):
    def test_orders_least_relevant_first(self) -> None:
        lo = ContextItem(content="lo", relevance=0.1)
        hi = ContextItem(content="hi", relevance=0.9)
        mid = ContextItem(content="mid", relevance=0.5)
        order = RelevanceEvictionPolicy().order_for_eviction((hi, lo, mid))
        assert [item.content for item in order] == ["lo", "mid", "hi"]


class TestImportance(unittest.TestCase):
    def test_orders_least_important_first(self) -> None:
        lo = ContextItem(content="lo", priority=1)
        hi = ContextItem(content="hi", priority=9)
        order = ImportanceEvictionPolicy().order_for_eviction((hi, lo))
        assert [item.content for item in order] == ["lo", "hi"]


class TestStability(unittest.TestCase):
    def test_ties_keep_input_order(self) -> None:
        a = ContextItem(content="a", priority=5)
        b = ContextItem(content="b", priority=5)
        c = ContextItem(content="c", priority=5)
        order = ImportanceEvictionPolicy().order_for_eviction((a, b, c))
        assert [item.content for item in order] == ["a", "b", "c"]


if __name__ == "__main__":
    unittest.main()
