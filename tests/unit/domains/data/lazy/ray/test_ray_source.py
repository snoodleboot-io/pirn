"""Tests for :class:`RaySource`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_source import RaySource


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
        self.assertEqual(src.path, "/tmp/data")

    def test_rejects_neither(self) -> None:
        with self.assertRaises(TypeError):
            RaySource(_config=KnotConfig(id="src"))

    def test_rejects_both(self) -> None:
        with self.assertRaises(TypeError):
            RaySource(
                factory=_make_dataset,
                path="/tmp/data",
                reader=lambda p: _make_dataset(),
                _config=KnotConfig(id="src"),
            )

    def test_path_without_reader_raises(self) -> None:
        with self.assertRaises(TypeError):
            RaySource(path="/tmp/data", _config=KnotConfig(id="src"))


class TestRaySourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_factory_emits_ray_dataset(self) -> None:
        src = RaySource(factory=_make_dataset, _config=KnotConfig(id="src"))
        result = await src.process(**{})
        self.assertIsInstance(result, RayDataset)

    async def test_reader_called_with_path(self) -> None:
        ds = _make_dataset()
        reader = MagicMock(return_value=ds)
        src = RaySource(
            path="/tmp/data",
            reader=reader,
            _config=KnotConfig(id="src"),
        )
        result = await src.process(**{})
        reader.assert_called_once_with("/tmp/data")
        self.assertIsInstance(result, RayDataset)
