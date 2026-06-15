"""Tests for :class:`RayCompute`."""

from __future__ import annotations

import pandas as pd
import pytest

pytestmark = pytest.mark.slow

ray = pytest.importorskip("ray")
ray_data = pytest.importorskip("ray.data")

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.ray.ray_compute import RayCompute
from pirn_data.lazy.ray.ray_execution_receipt import (
    RayExecutionReceipt,
)
from pirn_data.lazy.ray.ray_filter import RayFilter
from pirn_data.lazy.ray.ray_source import RaySource


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
async def test_compute_returns_receipt() -> None:
    with Tapestry() as t:
        src = RaySource(
            factory=_orders_factory, backend_name="ray",
            _config=KnotConfig(id="src"),
        )
        eu = RayFilter(
            batch=src,
            predicate=lambda row: row["region"] == "EU",
            _config=KnotConfig(id="eu"),
        )
        RayCompute(batch=eu, _config=KnotConfig(id="exec"))
    result = await t.run(RunRequest())
    receipt: RayExecutionReceipt = result.outputs["exec"]
    assert receipt.backend_name == "ray"
    assert receipt.target_path is None
    assert receipt.dataset_size == 3


@pytest.mark.asyncio
async def test_return_pandas_materialises_frame() -> None:
    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        eu = RayFilter(
            batch=src,
            predicate=lambda row: row["region"] == "EU",
            _config=KnotConfig(id="eu"),
        )
        RayCompute(
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
    target = str(tmp_path / "out_parquet")

    def _writer(ds, path: str) -> None:
        ds.write_parquet(path)

    with Tapestry() as t:
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        eu = RayFilter(
            batch=src,
            predicate=lambda row: row["region"] == "EU",
            _config=KnotConfig(id="eu"),
        )
        RayCompute(
            batch=eu,
            target_path=target,
            writer=_writer,
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    receipt: RayExecutionReceipt = result.outputs["exec"]
    assert receipt.target_path == target

    persisted = ray_data.read_parquet(target).take_all()
    assert len(persisted) == 3


def test_construct_rejects_target_without_writer() -> None:
    with Tapestry():
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="writer is required"):
            RayCompute(
                batch=src, target_path="/tmp/x_parquet",
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_empty_target() -> None:
    with Tapestry():
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(ValueError, match="non-empty"):
            RayCompute(
                batch=src, target_path="", writer=lambda ds, p: None,
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_pandas_with_target() -> None:
    with Tapestry():
        src = RaySource(factory=_orders_factory, _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="mutually exclusive"):
            RayCompute(
                batch=src,
                target_path="/tmp/x_parquet",
                writer=lambda ds, p: None,
                return_pandas=True,
                _config=KnotConfig(id="x"),
            )
