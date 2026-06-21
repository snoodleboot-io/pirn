"""Tests for :class:`RayMap`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.ray.ray_dataset import RayDataset
from pirn_data.lazy.ray.ray_map import RayMap
from pirn_data.lazy.ray.ray_source import RaySource


def _items_factory():
    return ray_data.from_items(
        [{"id": 1, "x": 1}, {"id": 2, "x": 2}, {"id": 3, "x": 3}]
    )


def _double_x(batch):
    # batch is a dict[str, np.ndarray] under the "numpy" batch_format.
    batch["x2"] = batch["x"] * 2
    return batch


@pytest.mark.asyncio
async def test_map_batches_doubles_column() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_items_factory, _config=KnotConfig(id="src"))
        RayMap(
            batch=src,
            fn=_double_x,
            batch_format="numpy",
            _config=KnotConfig(id="doubled"),
        )
    result = await t.run(RunRequest())
    out: RayDataset = result.outputs["doubled"]
    rows = out.dataset.take_all()
    pairs = sorted((r["x"], r["x2"]) for r in rows)
    assert pairs == [(1, 2), (2, 4), (3, 6)]


def test_construct_rejects_non_callable_fn() -> None:
    with Tapestry():
        src = RaySource(factory=_items_factory, _config=KnotConfig(id="s"))
        with pytest.raises(TypeError, match="callable"):
            RayMap(
                batch=src, fn="double",  # type: ignore[arg-type]
                _config=KnotConfig(id="m"),
            )


def test_construct_rejects_invalid_batch_size() -> None:
    with Tapestry():
        src = RaySource(factory=_items_factory, _config=KnotConfig(id="s"))
        with pytest.raises(ValueError, match="positive int"):
            RayMap(
                batch=src, fn=_double_x, batch_size=0,
                _config=KnotConfig(id="m"),
            )
