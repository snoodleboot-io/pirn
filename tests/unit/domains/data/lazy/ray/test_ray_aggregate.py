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
from pirn.core.knot_factory import knot
from pirn.domains.data.lazy.ray.ray_aggregate import RayAggregate
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

import pytest

pytestmark = pytest.mark.slow


def _make_batch() -> RayDataset:
    ds = ray.data.from_items([{"region": "EU", "amount": 10}, {"region": "US", "amount": 5}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _make_batch()


class TestRayAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_aggregator_mode_happy_path(self) -> None:
        batch = _make_batch()
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(
                batch=src,
                aggregator=lambda ds: ds,
                _config=KnotConfig(id="agg"),
            )
        result = await agg.process(
            batch=batch,
            aggregator=lambda ds: ds,
            by=None,
            aggs=None,
        )
        self.assertIsInstance(result, RayDataset)

    async def test_declarative_mode_happy_path(self) -> None:
        batch = _make_batch()
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(
                batch=src,
                by="region",
                aggs=[Sum("amount")],
                _config=KnotConfig(id="agg"),
            )
        result = await agg.process(
            batch=batch,
            aggregator=None,
            by="region",
            aggs=[Sum("amount")],
        )
        self.assertIsInstance(result, RayDataset)

    async def test_declarative_mode_list_by(self) -> None:
        batch = _make_batch()
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            agg = RayAggregate(
                batch=src,
                by=["region"],
                aggs=[Sum("amount")],
                _config=KnotConfig(id="agg"),
            )
        result = await agg.process(
            batch=batch,
            aggregator=None,
            by=["region"],
            aggs=[Sum("amount")],
        )
        self.assertIsInstance(result, RayDataset)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_aggregator_from_upstream_knot(self) -> None:
        @knot
        async def emit_batch() -> RayDataset:
            return _make_batch()

        @knot
        async def emit_agg() -> Any:
            return lambda ds: ds

        with Tapestry():
            batch = emit_batch(_config=KnotConfig(id="batch"))
            agg_knot = emit_agg(_config=KnotConfig(id="agg_fn"))
            RayAggregate(
                batch=batch,
                aggregator=agg_knot,
                _config=KnotConfig(id="agg"),
            )
        # Construction with Knot inputs succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> RayAggregate:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            return RayAggregate(
                batch=src,
                aggregator=lambda ds: ds,
                _config=KnotConfig(id="agg"),
                **kwargs,
            )

    async def test_rejects_neither_aggregator_nor_by(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "either aggregator"):
            await k.process(
                batch=_make_batch(),
                aggregator=None,
                by=None,
                aggs=None,
            )

    async def test_rejects_aggregator_with_by(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            await k.process(
                batch=_make_batch(),
                aggregator=lambda ds: ds,
                by="region",
                aggs=None,
            )

    async def test_rejects_non_callable_aggregator(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_make_batch(),
                aggregator="not-callable",
                by=None,
                aggs=None,
            )

    async def test_rejects_empty_by_string(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_batch(),
                aggregator=None,
                by="",
                aggs=[Sum("amount")],
            )

    async def test_rejects_by_without_aggs(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "aggs is required"):
            await k.process(
                batch=_make_batch(),
                aggregator=None,
                by="region",
                aggs=None,
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_batch(),
                aggregator=None,
                by="region",
                aggs=[],
            )
