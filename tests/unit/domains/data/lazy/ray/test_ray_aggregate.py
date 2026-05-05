"""Tests for :class:`RayAggregate`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import ray.data
    from ray.data.aggregate import Sum
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_aggregate import RayAggregate
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        ds = ray.data.from_items([{"region": "EU", "amount": 10}])
        return RayDataset(dataset=ds)


class TestRayAggregateConstruction(unittest.TestCase):
    def test_aggregator_mode(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(batch=src, aggregator=lambda ds: ds, _config=KnotConfig(id="agg"))
        self.assertIsInstance(agg, RayAggregate)

    def test_declarative_mode_string_by(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(
                batch=src,
                by="region",
                aggs=[Sum("amount")],
                _config=KnotConfig(id="agg"),
            )
        self.assertEqual(agg.by, "region")

    def test_rejects_neither(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayAggregate(batch=src, _config=KnotConfig(id="agg"))

    def test_rejects_aggregator_with_by(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayAggregate(batch=src, aggregator=lambda ds: ds, by="region", _config=KnotConfig(id="agg"))

    def test_rejects_by_without_aggs(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayAggregate(batch=src, by="region", _config=KnotConfig(id="agg"))


class TestRayAggregateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_aggregator_mode_process(self) -> None:
        ds = ray.data.from_items([{"region": "EU", "amount": 10}])
        batch = RayDataset(dataset=ds)
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(batch=src, aggregator=lambda ds: ds, _config=KnotConfig(id="agg"))
        result = await agg.process(batch=batch)
        self.assertIsInstance(result, RayDataset)
