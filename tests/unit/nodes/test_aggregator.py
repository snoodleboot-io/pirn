"""Unit tests for Aggregator."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ValSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class TestAggregatorConstruction(unittest.TestCase):
    def test_rejects_non_callable_combine(self) -> None:
        with self.assertRaisesRegex(TypeError, "combine"):
            with Tapestry():
                a = _ValSource(value=1, _config=KnotConfig(id="a"))
                Aggregator(combine="not_callable", a=a, _config=KnotConfig(id="agg"))

    def test_rejects_no_parents(self) -> None:
        with self.assertRaisesRegex(TypeError, "at least one parent"):
            with Tapestry():
                Aggregator(combine=sum, _config=KnotConfig(id="agg"))

    def test_rejects_non_knot_parent(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a Knot"):
            with Tapestry():
                Aggregator(combine=sum, a=42, _config=KnotConfig(id="agg"))

    def test_rejects_missing_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "_config"):
            with Tapestry():
                a = _ValSource(value=1, _config=KnotConfig(id="a"))
                Aggregator(combine=sum, a=a)


class TestAggregatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_sync_combine_merges_dicts(self) -> None:
        def merge(a: dict, b: dict) -> dict:
            return {**a, **b}

        with Tapestry() as t:
            ka = _ValSource(value={"x": 1}, _config=KnotConfig(id="a"))
            kb = _ValSource(value={"y": 2}, _config=KnotConfig(id="b"))
            Aggregator(combine=merge, a=ka, b=kb, _config=KnotConfig(id="agg"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["agg"], {"x": 1, "y": 2})

    async def test_async_combine_is_awaited(self) -> None:
        async def async_merge(a: int, b: int) -> int:
            return a + b

        with Tapestry() as t:
            ka = _ValSource(value=3, _config=KnotConfig(id="a"))
            kb = _ValSource(value=4, _config=KnotConfig(id="b"))
            Aggregator(combine=async_merge, a=ka, b=kb, _config=KnotConfig(id="agg"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["agg"], 7)

    async def test_single_parent_aggregator(self) -> None:
        with Tapestry() as t:
            ka = _ValSource(value=[1, 2, 3], _config=KnotConfig(id="a"))
            Aggregator(combine=lambda a: sum(a), a=ka, _config=KnotConfig(id="agg"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["agg"], 6)
