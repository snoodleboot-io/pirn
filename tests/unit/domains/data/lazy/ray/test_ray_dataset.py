"""Tests for :class:`RayDataset`."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

try:
    import ray.data
except ImportError as _e:
    raise unittest.SkipTest("ray not installed") from _e

from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


def _make_ray_dataset() -> ray.data.Dataset:
    return ray.data.from_items([{"x": 1}, {"x": 2}])


class TestRayDataset(unittest.TestCase):
    def test_construction_defaults(self) -> None:
        ds = _make_ray_dataset()
        rds = RayDataset(dataset=ds)
        self.assertEqual(rds.backend_name, "ray")
        self.assertEqual(rds.source_uri, "")
        self.assertIsInstance(rds.fetched_at, datetime)

    def test_with_dataset_preserves_metadata(self) -> None:
        ds = _make_ray_dataset()
        now = datetime.now(timezone.utc)
        rds = RayDataset(dataset=ds, backend_name="custom", source_uri="s3://b/k", fetched_at=now)
        new_ds = _make_ray_dataset()
        rds2 = rds.with_dataset(new_ds)
        self.assertEqual(rds2.backend_name, "custom")
        self.assertEqual(rds2.source_uri, "s3://b/k")
        self.assertEqual(rds2.fetched_at, now)

    def test_frozen(self) -> None:
        ds = _make_ray_dataset()
        rds = RayDataset(dataset=ds)
        with self.assertRaises((AttributeError, TypeError)):
            rds.backend_name = "other"  # type: ignore[misc]
