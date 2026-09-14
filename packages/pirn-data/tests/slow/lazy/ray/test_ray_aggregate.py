"""Tests for :class:`RayAggregate`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from ray.data.aggregate import Sum

from pirn_data.lazy.ray.ray_aggregate import RayAggregate
from pirn_data.lazy.ray.ray_dataset import RayDataset
from pirn_data.lazy.ray.ray_source import RaySource


def _orders_factory():
    return ray_data.from_items(
        [
            {"region": "EU", "amount": 10.0},
            {"region": "EU", "amount": 25.0},
            {"region": "EU", "amount": 5.0},
            {"region": "US", "amount": 100.0},
            {"region": "US", "amount": 50.0},
        ]
    )


@pytest.mark.asyncio
async def test_declarative_groupby_sum() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        RayAggregate(
            batch=src,
            by="region",
            aggs=[Sum("amount")],
            _config=KnotConfig(id="totals"),
        )
    result = await t.run(RunRequest())
    out: RayDataset = result.outputs["totals"]
    rows = out.dataset.take_all()
    by_region = {r["region"]: r for r in rows}
    eu_total = next(v for k, v in by_region["EU"].items() if "sum" in k.lower())
    us_total = next(v for k, v in by_region["US"].items() if "sum" in k.lower())
    assert eu_total == 40.0
    assert us_total == 150.0


@pytest.mark.asyncio
async def test_aggregator_callable() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        RayAggregate(
            batch=src,
            aggregator=lambda ds: ds.groupby("region").sum("amount"),
            _config=KnotConfig(id="totals"),
        )
    result = await t.run(RunRequest())
    out: RayDataset = result.outputs["totals"]
    rows = out.dataset.take_all()
    assert len(rows) == 2
