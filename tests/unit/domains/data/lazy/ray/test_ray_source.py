"""Tests for :class:`RaySource`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_source import RaySource

pytestmark = pytest.mark.slow


def _make_dataset() -> ray.data.Dataset:
    return ray.data.from_items([{"x": 1}])


class TestRaySourceConstruction(unittest.TestCase):
    def test_factory_mode(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        self.assertIsInstance(src, RaySource)

    def test_path_mode(self) -> None:
        src = RaySource(
            path="/tmp/data",
            reader=lambda p: _make_dataset(),
            _config=KnotConfig(id="src"),
        )
        self.assertIsInstance(src, RaySource)


class TestRaySourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_factory_emits_ray_dataset(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        result = await src.process(factory=_make_dataset)
        self.assertIsInstance(result, RayDataset)

    async def test_reader_called_with_path(self) -> None:
        ds = _make_dataset()
        reader = MagicMock(return_value=ds)
        src = RaySource(
            path="/tmp/data",
            reader=reader,
            _config=KnotConfig(id="src"),
        )
        result = await src.process(path="/tmp/data", reader=reader)
        reader.assert_called_once_with("/tmp/data")
        self.assertIsInstance(result, RayDataset)

    async def test_rejects_neither(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process()

    async def test_rejects_both(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process(factory=_make_dataset, path="/tmp/data", reader=lambda p: _make_dataset())

    async def test_path_without_reader_raises(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process(path="/tmp/data")

    async def test_source_uri_defaults_to_path(self) -> None:
        ds = _make_dataset()
        reader = MagicMock(return_value=ds)
        src = RaySource(
            path="/tmp/data",
            reader=reader,
            _config=KnotConfig(id="src"),
        )
        result = await src.process(path="/tmp/data", reader=reader)
        self.assertEqual(result.source_uri, "/tmp/data")
