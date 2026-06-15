"""Tests for :class:`DaskCompute`."""

from __future__ import annotations

import dask.dataframe as dd
import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.dask.dask_compute import DaskCompute
from pirn_data.lazy.dask.dask_execution_receipt import (
    DaskExecutionReceipt,
)
from pirn_data.lazy.dask.dask_filter import DaskFilter
from pirn_data.lazy.dask.dask_source import DaskSource


def _orders_factory() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {
            "id":     [1, 2, 3, 4],
            "amount": [10.0, 25.0, 5.0, 100.0],
            "region": ["EU", "EU", "EU", "US"],
        }
    )
    return dd.from_pandas(pdf, npartitions=2)


@pytest.mark.asyncio
async def test_compute_returns_receipt() -> None:
    with Tapestry() as t:
        src = DaskSource(
            factory=_orders_factory, backend_name="dask",
            _config=KnotConfig(id="src"),
        )
        eu = DaskFilter(
            batch=src,
            predicate=lambda frame: frame.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        DaskCompute(batch=eu, _config=KnotConfig(id="exec"))
    result = await t.run(RunRequest())
    receipt: DaskExecutionReceipt = result.outputs["exec"]
    assert receipt.backend_name == "dask"
    assert receipt.target_path is None
    assert receipt.row_count == 3
    assert receipt.partitions_executed >= 1


@pytest.mark.asyncio
async def test_return_pandas_materialises_frame() -> None:
    with Tapestry() as t:
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        eu = DaskFilter(
            batch=src,
            predicate=lambda frame: frame.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        DaskCompute(
            batch=eu,
            return_pandas=True,
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    out = result.outputs["exec"]
    assert isinstance(out, pd.DataFrame)
    assert len(out) == 3


@pytest.mark.asyncio
async def test_compute_writes_target_path(tmp_path) -> None:
    target = str(tmp_path / "out.parquet")

    def _writer(frame: dd.DataFrame, path: str) -> None:
        frame.to_parquet(path)

    with Tapestry() as t:
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        eu = DaskFilter(
            batch=src,
            predicate=lambda frame: frame.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        DaskCompute(
            batch=eu,
            target_path=target,
            writer=_writer,
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    receipt: DaskExecutionReceipt = result.outputs["exec"]
    assert receipt.target_path == target
    persisted = dd.read_parquet(target).compute()
    assert len(persisted) == 3


def test_construct_rejects_target_without_writer() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="writer is required"):
            DaskCompute(
                batch=src, target_path="/tmp/x.parquet",
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_empty_target() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(ValueError, match="non-empty"):
            DaskCompute(
                batch=src, target_path="", writer=lambda f, p: None,
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_pandas_with_target() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="mutually exclusive"):
            DaskCompute(
                batch=src,
                target_path="/tmp/x.parquet",
                writer=lambda f, p: None,
                return_pandas=True,
                _config=KnotConfig(id="x"),
            )
