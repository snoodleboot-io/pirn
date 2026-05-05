"""Tests for :class:`RayFilter`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_filter import RayFilter
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _make_batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}, {"x": 3}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _make_batch()


class TestRayFilterConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            flt = RayFilter(batch=src, predicate=lambda row: row["x"] > 1, _config=KnotConfig(id="flt"))
        self.assertIsInstance(flt, RayFilter)

    def test_rejects_non_callable(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayFilter(
                    batch=src,
                    predicate="not-callable",  # type: ignore[arg-type]
                    _config=KnotConfig(id="flt"),
                )


class TestRayFilterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_filters_rows(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            flt = RayFilter(batch=src, predicate=lambda row: row["x"] > 1, _config=KnotConfig(id="flt"))
        result = await flt.process(batch=_make_batch())
        self.assertIsInstance(result, RayDataset)
        rows = result.dataset.take_all()
        self.assertEqual(len(rows), 2)
