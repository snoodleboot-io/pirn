"""Tests for :class:`RaySource`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_data.lazy.ray.ray_dataset import RayDataset
from pirn_data.lazy.ray.ray_source import RaySource


def _people_factory():
    return ray_data.from_items([{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}])


@pytest.mark.asyncio
async def test_ray_source_emits_deferred_dataset() -> None:
    with Tapestry() as t:
        RaySource(
            factory=_people_factory,
            backend_name="ray",
            _config=KnotConfig(id="people"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded
    out: RayDataset = result.outputs["people"]
    assert out.backend_name == "ray"


def test_construct_rejects_non_callable_factory() -> None:
    with pytest.raises(TypeError, match="callable"):
        RaySource(factory="not callable", _config=KnotConfig(id="x"))
