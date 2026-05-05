"""Tests for :class:`RayCompute`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_compute import RayCompute
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_execution_receipt import RayExecutionReceipt
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _batch()


class TestRayComputeConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(batch=src, _config=KnotConfig(id="compute"))
        self.assertIsNone(rc.target_path)
        self.assertFalse(rc.return_pandas)

    def test_path_requires_writer(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayCompute(batch=src, target_path="/tmp/out", _config=KnotConfig(id="compute"))

    def test_return_pandas_exclusive_with_path(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                RayCompute(
                    batch=src,
                    target_path="/tmp/out",
                    writer=lambda ds, p: None,
                    return_pandas=True,
                    _config=KnotConfig(id="compute"),
                )


class TestRayComputeProcess(unittest.IsolatedAsyncioTestCase):
    async def test_default_returns_receipt(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(batch=src, _config=KnotConfig(id="compute"))
        result = await rc.process(batch=_batch())
        self.assertIsInstance(result, RayExecutionReceipt)

    async def test_writer_mode(self) -> None:
        writer = MagicMock()
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(
                batch=src,
                target_path="/tmp/out",
                writer=writer,
                _config=KnotConfig(id="compute"),
            )
        result = await rc.process(batch=_batch())
        writer.assert_called_once()
        self.assertEqual(result.target_path, "/tmp/out")
