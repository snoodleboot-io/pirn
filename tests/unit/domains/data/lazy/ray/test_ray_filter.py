"""Tests for :class:`RayFilter`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.lazy.ray.ray_dataset import RayDataset
from pirn_data.lazy.ray.ray_filter import RayFilter

pytestmark = pytest.mark.slow


def _make_batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}, {"x": 3}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _make_batch()


class TestRayFilter(unittest.IsolatedAsyncioTestCase):
    async def test_filters_rows_happy_path(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            flt = RayFilter(
                batch=src,
                predicate=lambda row: row["x"] > 1,
                _config=KnotConfig(id="flt"),
            )
        result = await flt.process(
            batch=_make_batch(),
            predicate=lambda row: row["x"] > 1,
        )
        self.assertIsInstance(result, RayDataset)
        rows = result.dataset.take_all()
        self.assertEqual(len(rows), 2)

    async def test_filter_keeps_all_rows(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            flt = RayFilter(
                batch=src,
                predicate=lambda row: True,
                _config=KnotConfig(id="flt"),
            )
        result = await flt.process(
            batch=_make_batch(),
            predicate=lambda row: True,
        )
        rows = result.dataset.take_all()
        self.assertEqual(len(rows), 3)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_batch() -> RayDataset:
            return _make_batch()

        @knot
        async def emit_predicate() -> Any:
            return lambda row: row["x"] == 1

        with Tapestry():
            batch = emit_batch(_config=KnotConfig(id="batch"))
            pred = emit_predicate(_config=KnotConfig(id="pred"))
            RayFilter(batch=batch, predicate=pred, _config=KnotConfig(id="flt"))
        # Construction with Knot inputs succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> RayFilter:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            return RayFilter(
                batch=src,
                predicate=lambda row: True,
                _config=KnotConfig(id="flt"),
                **kwargs,
            )

    async def test_rejects_non_callable_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(batch=_make_batch(), predicate="not-callable")
