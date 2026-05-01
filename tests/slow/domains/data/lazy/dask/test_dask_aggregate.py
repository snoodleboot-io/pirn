"""Tests for :class:`DaskAggregate`."""

from __future__ import annotations

import dask.dataframe as dd
import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_aggregate import DaskAggregate
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_source import DaskSource
from pirn.tapestry import Tapestry


def _orders_factory() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {
            "region":   ["EU", "EU", "EU", "US", "US"],
            "amount":   [10.0, 25.0, 5.0, 100.0, 50.0],
            "customer": ["alice", "bob", "alice", "carol", "carol"],
        }
    )
    return dd.from_pandas(pdf, npartitions=2)


@pytest.mark.asyncio
async def test_declarative_by_aggs() -> None:
    with Tapestry() as t:
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        DaskAggregate(
            batch=src,
            by=("region",),
            aggs={"amount": "sum"},
            _config=KnotConfig(id="totals"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["totals"]
    rows = out.frame.compute().set_index("region")
    assert rows.loc["EU", "amount"] == 40.0
    assert rows.loc["US", "amount"] == 150.0


@pytest.mark.asyncio
async def test_aggregator_callable() -> None:
    with Tapestry() as t:
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        DaskAggregate(
            batch=src,
            aggregator=lambda frame: (
                frame.groupby("region").amount.sum().reset_index()
            ),
            _config=KnotConfig(id="totals"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["totals"]
    rows = out.frame.compute().set_index("region")
    assert rows.loc["EU", "amount"] == 40.0
    assert rows.loc["US", "amount"] == 150.0


def test_construct_rejects_neither() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="aggregator or"):
            DaskAggregate(batch=src, _config=KnotConfig(id="g"))


def test_construct_rejects_aggregator_with_by() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="mutually exclusive"):
            DaskAggregate(
                batch=src,
                aggregator=lambda f: f,
                by=("region",),
                aggs={"amount": "sum"},
                _config=KnotConfig(id="g"),
            )


def test_construct_rejects_string_by() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="sequence"):
            DaskAggregate(
                batch=src,
                by="region",  # type: ignore[arg-type]
                aggs={"amount": "sum"},
                _config=KnotConfig(id="g"),
            )


def test_construct_rejects_empty_by() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(ValueError, match="non-empty"):
            DaskAggregate(
                batch=src,
                by=(),
                aggs={"amount": "sum"},
                _config=KnotConfig(id="g"),
            )


def test_construct_rejects_missing_aggs() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="aggs is required"):
            DaskAggregate(
                batch=src,
                by=("region",),
                _config=KnotConfig(id="g"),
            )
