"""Tests for :class:`RayDataset`."""

from __future__ import annotations

from datetime import UTC

import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")

from pirn_data.lazy.ray.ray_dataset import RayDataset


def _people_dataset():
    return ray_data.from_items(
        [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
    )


class TestRayDataset:
    def test_default_fetched_at_is_utc(self) -> None:
        batch = RayDataset(dataset=_people_dataset())
        assert batch.fetched_at.tzinfo is UTC

    def test_with_dataset_preserves_metadata(self) -> None:
        original = RayDataset(
            dataset=_people_dataset(),
            backend_name="ray",
            source_uri="memory://people",
        )
        replaced = original.with_dataset(_people_dataset())
        assert replaced.backend_name == "ray"
        assert replaced.source_uri == "memory://people"
        assert replaced.fetched_at == original.fetched_at
