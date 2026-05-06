"""Tests for :class:`RayCompute`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.data.lazy.ray.ray_compute import RayCompute
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_execution_receipt import RayExecutionReceipt
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.slow


def _batch() -> RayDataset:
    ds = ray.data.from_items([{"x": 1}, {"x": 2}])
    return RayDataset(dataset=ds)


class _RaySource(Source):
    async def process(self, **_: Any) -> RayDataset:
        return _batch()


class TestRayCompute(unittest.IsolatedAsyncioTestCase):
    async def test_default_materialise_returns_receipt(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(batch=src, _config=KnotConfig(id="compute"))
        result = await rc.process(
            batch=_batch(),
            target_path=None,
            writer=None,
            writer_kwargs=None,
            return_pandas=False,
        )
        self.assertIsInstance(result, RayExecutionReceipt)
        self.assertIsNone(result.target_path)

    async def test_writer_mode_returns_receipt(self) -> None:
        writer = MagicMock()
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(
                batch=src,
                target_path="/tmp/out",
                writer=writer,
                _config=KnotConfig(id="compute"),
            )
        result = await rc.process(
            batch=_batch(),
            target_path="/tmp/out",
            writer=writer,
            writer_kwargs=None,
            return_pandas=False,
        )
        writer.assert_called_once()
        self.assertIsInstance(result, RayExecutionReceipt)
        self.assertEqual(result.target_path, "/tmp/out")

    async def test_return_pandas_mode(self) -> None:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            rc = RayCompute(batch=src, return_pandas=True, _config=KnotConfig(id="compute"))
        result = await rc.process(
            batch=_batch(),
            target_path=None,
            writer=None,
            writer_kwargs=None,
            return_pandas=True,
        )
        # pandas DataFrame has a shape attribute
        self.assertTrue(hasattr(result, "shape"))


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_return_pandas_from_upstream_knot(self) -> None:
        @knot
        async def emit_flag() -> bool:
            return False

        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            flag = emit_flag(_config=KnotConfig(id="flag"))
            RayCompute(batch=src, return_pandas=flag, _config=KnotConfig(id="compute"))
        # Construction with Knot input succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> RayCompute:
        with Tapestry():
            src = _RaySource(_config=KnotConfig(id="src"))
            return RayCompute(batch=src, _config=KnotConfig(id="compute"), **kwargs)

    async def test_rejects_empty_target_path(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_batch(),
                target_path="",
                writer=MagicMock(),
                writer_kwargs=None,
                return_pandas=False,
            )

    async def test_rejects_path_without_writer(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "writer is required"):
            await k.process(
                batch=_batch(),
                target_path="/tmp/out",
                writer=None,
                writer_kwargs=None,
                return_pandas=False,
            )

    async def test_rejects_non_callable_writer(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_batch(),
                target_path="/tmp/out",
                writer="not-callable",
                writer_kwargs=None,
                return_pandas=False,
            )

    async def test_rejects_return_pandas_with_path(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            await k.process(
                batch=_batch(),
                target_path="/tmp/out",
                writer=MagicMock(),
                writer_kwargs=None,
                return_pandas=True,
            )
