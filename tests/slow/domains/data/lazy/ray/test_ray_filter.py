"""Tests for :class:`RayFilter`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_filter import RayFilter
from pirn.domains.data.lazy.ray.ray_source import RaySource
from pirn.tapestry import Tapestry


def _orders_factory():
    return ray_data.from_items(
        [
            {"id": 1, "amount": 10.0, "region": "EU"},
            {"id": 2, "amount": 25.0, "region": "EU"},
            {"id": 3, "amount": 5.0,  "region": "EU"},
            {"id": 4, "amount": 100.0, "region": "US"},
        ]
    )


@pytest.mark.asyncio
async def test_filter_keeps_dataset_deferred() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        RayFilter(
            batch=src,
            predicate=lambda row: row["region"] == "EU",
            _config=KnotConfig(id="eu"),
        )
    result = await t.run(RunRequest())
    out: RayDataset = result.outputs["eu"]
    rows = out.dataset.take_all()
    assert len(rows) == 3
    assert all(r["region"] == "EU" for r in rows)


@pytest.mark.asyncio
async def test_filter_chains() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        active = RayFilter(
            batch=src,
            predicate=lambda row: row["region"] == "EU",
            _config=KnotConfig(id="eu"),
        )
        RayFilter(
            batch=active,
            predicate=lambda row: row["amount"] > 5.0,
            _config=KnotConfig(id="big_eu"),
        )
    result = await t.run(RunRequest())
    out: RayDataset = result.outputs["big_eu"]
    rows = out.dataset.take_all()
    assert len(rows) == 2


def test_construct_rejects_non_callable_predicate() -> None:
    with Tapestry():
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="s"))
        with pytest.raises(TypeError, match="callable"):
            RayFilter(
                batch=src,
                predicate="region == 'EU'",  # type: ignore[arg-type]
                _config=KnotConfig(id="f"),
            )
