"""Tests for :class:`RayMap`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_map import RayMap
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _make_batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _make_batch()


class TestRayMapConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rm = RayMap(batch=src, fn=lambda b: b, _config=KnotConfig(id="map"))
        self.assertIsInstance(rm, RayMap)

    def test_rejects_non_callable_fn(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayMap(batch=src, fn="not-callable", _config=KnotConfig(id="map"))  # type: ignore[arg-type]

    def test_rejects_invalid_batch_size(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                RayMap(batch=src, fn=lambda b: b, batch_size=0, _config=KnotConfig(id="map"))


class TestRayMapProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_ray_dataset(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rm = RayMap(
                batch=src,
                fn=lambda b: {"x": [v * 2 for v in b["x"]]},
                batch_format="numpy",
                _config=KnotConfig(id="map"),
            )
        result = await rm.process(batch=_make_batch())
        self.assertIsInstance(result, RayDataset)
