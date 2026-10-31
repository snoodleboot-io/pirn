"""Unit tests for :class:`RecalledReflection`.

The per-key read behind :class:`ReflexionLoop`'s reflection fan-out (PIR-874).
Each read is its own knot, so a missing key has to be a *value* the aggregator
can drop rather than a failure that takes the iteration down with it.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.reflexion.recalled_reflection import RecalledReflection
from pirn_agents.specializations.reflexion.reflexion_loop import ReflexionLoop


class _DictStore(MemoryStore):
    """A ``MemoryStore`` over a dict, so ``retrieve`` answers what was stored."""

    def __init__(self, entries: Mapping[str, Mapping[str, Any]]) -> None:
        self._entries = {key: dict(value) for key, value in entries.items()}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self._entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self._entries.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        return []

    async def forget(self, key: str) -> None:
        self._entries.pop(key, None)

    async def close(self) -> None:
        return None


def _make_knot(memory: MemoryStore, key: str) -> RecalledReflection:
    with Tapestry():
        return RecalledReflection(memory=memory, key=key, _config=KnotConfig(id="reflection_0"))


class TestRecalledReflection(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_stored_text(self) -> None:
        memory = _DictStore({"ns:0": {"text": "try shorter answers"}})
        knot = _make_knot(memory, "ns:0")
        assert await knot.process(memory=memory, key="ns:0") == "try shorter answers"

    async def test_an_absent_key_is_none_not_a_failure(self) -> None:
        memory = _DictStore({})
        knot = _make_knot(memory, "ns:0")
        assert await knot.process(memory=memory, key="ns:0") is None

    async def test_an_entry_without_a_text_string_is_none(self) -> None:
        memory = _DictStore({"ns:0": {"text": 7}, "ns:1": {"other": "x"}})
        knot = _make_knot(memory, "ns:0")
        assert await knot.process(memory=memory, key="ns:0") is None
        assert await knot.process(memory=memory, key="ns:1") is None


class TestReflectionsReachTheActorInOrder(unittest.TestCase):
    """The aggregator restores key order whatever order the engine read them in."""

    def test_sorts_by_index_and_drops_the_gaps(self) -> None:
        combined = ReflexionLoop._in_key_order(
            reflection_2="third",
            reflection_0="first",
            reflection_1=None,
        )
        assert combined == ("first", "third")

    def test_double_digit_indices_sort_numerically(self) -> None:
        """String order would put ``reflection_10`` before ``reflection_2``."""
        combined = ReflexionLoop._in_key_order(
            **{f"reflection_{index}": f"r{index}" for index in range(12)}
        )
        assert combined == tuple(f"r{index}" for index in range(12))
