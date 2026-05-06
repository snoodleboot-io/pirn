"""Tests for :class:`RayMap`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_map import RayMap
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

import pytest

pytestmark = pytest.mark.slow


def _make_batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _make_batch()


class TestRayMap(unittest.IsolatedAsyncioTestCase):
    async def test_returns_ray_dataset(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rm = RayMap(
                batch=src,
                fn=lambda b: {"x": [v * 2 for v in b["x"]]},
                batch_format="numpy",
                _config=KnotConfig(id="map"),
            )
        result = await rm.process(
            batch=_make_batch(),
            fn=lambda b: {"x": [v * 2 for v in b["x"]]},
            batch_format="numpy",
            batch_size=None,
        )
        self.assertIsInstance(result, RayDataset)

    async def test_no_optional_params(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rm = RayMap(batch=src, fn=lambda b: b, _config=KnotConfig(id="map"))
        result = await rm.process(
            batch=_make_batch(),
            fn=lambda b: b,
            batch_format=None,
            batch_size=None,
        )
        self.assertIsInstance(result, RayDataset)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_fn_from_upstream_knot(self) -> None:
        @knot
        async def emit_fn() -> Any:
            return lambda b: b

        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            fn_knot = emit_fn(_config=KnotConfig(id="fn"))
            RayMap(batch=src, fn=fn_knot, _config=KnotConfig(id="map"))
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> RayMap:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            return RayMap(
                batch=src,
                fn=lambda b: b,
                _config=KnotConfig(id="map"),
                **kwargs,
            )

    async def test_rejects_non_callable_fn(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_make_batch(),
                fn="not-callable",
                batch_format=None,
                batch_size=None,
            )

    async def test_rejects_non_string_batch_format(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await k.process(
                batch=_make_batch(),
                fn=lambda b: b,
                batch_format=123,  # type: ignore[arg-type]
                batch_size=None,
            )

    async def test_rejects_zero_batch_size(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await k.process(
                batch=_make_batch(),
                fn=lambda b: b,
                batch_format=None,
                batch_size=0,
            )

    async def test_rejects_negative_batch_size(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await k.process(
                batch=_make_batch(),
                fn=lambda b: b,
                batch_format=None,
                batch_size=-1,
            )
