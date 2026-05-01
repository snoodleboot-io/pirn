"""Tests for :class:`SparkCompute`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.spark.spark_compute import SparkCompute
from pirn.domains.data.lazy.spark.spark_execution_receipt import (
    SparkExecutionReceipt,
)
from pirn.domains.data.lazy.spark.spark_filter import SparkFilter
from pirn.domains.data.lazy.spark.spark_source import SparkSource
from pirn.tapestry import Tapestry


def _orders_query() -> str:
    return (
        "SELECT * FROM VALUES "
        "(1, 10.0, 'EU'), (2, 25.0, 'EU'), (3, 5.0, 'EU'), (4, 100.0, 'US') "
        "AS t(id, amount, region)"
    )


@pytest.mark.asyncio
async def test_compute_collect_returns_rows(_spark_session) -> None:
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        eu = SparkFilter(
            frame=src,
            predicate="region = 'EU'",
            _config=KnotConfig(id="eu"),
        )
        SparkCompute(frame=eu, _config=KnotConfig(id="exec"))
    result = await t.run(RunRequest())
    rows = result.outputs["exec"]
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert all(row["region"] == "EU" for row in rows)


@pytest.mark.asyncio
async def test_compute_writes_path(tmp_path, _spark_session) -> None:
    target = str(tmp_path / "eu_orders.parquet")
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        eu = SparkFilter(
            frame=src,
            predicate="region = 'EU'",
            _config=KnotConfig(id="eu"),
        )
        SparkCompute(
            frame=eu,
            path=target,
            format="parquet",
            mode="overwrite",
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    receipt = result.outputs["exec"]
    assert isinstance(receipt, SparkExecutionReceipt)
    assert receipt.succeeded is True
    assert receipt.output_path == target
    # Sanity: read back the persisted parquet via Spark.
    persisted = _spark_session.read.format("parquet").load(target)
    assert persisted.count() == 3


def test_construct_rejects_empty_path(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="non-empty"):
            SparkCompute(
                frame=src,
                path="",
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_empty_format(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="format"):
            SparkCompute(
                frame=src,
                path="/tmp/x",
                format="",
                _config=KnotConfig(id="x"),
            )
