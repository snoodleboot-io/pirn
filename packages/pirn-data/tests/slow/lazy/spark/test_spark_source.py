"""Tests for :class:`SparkSource`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn_data.lazy.spark.spark_source import SparkSource


def _write_parquet(session, tmp_path) -> str:
    target = str(tmp_path / "orders.parquet")
    frame = session.createDataFrame(
        [(1, 10.0, "EU"), (2, 25.0, "EU"), (3, 5.0, "US")],
        ["id", "amount", "region"],
    )
    frame.write.mode("overwrite").format("parquet").save(target)
    return target


@pytest.mark.asyncio
async def test_source_reads_parquet(tmp_path, _spark_session) -> None:
    target = _write_parquet(_spark_session, tmp_path)
    with Tapestry() as t:
        SparkSource(
            spark_session=_spark_session,
            format="parquet",
            path=target,
            _config=KnotConfig(id="src"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["src"]
    assert isinstance(out, SparkDataFrame)
    assert set(out.column_names) == {"id", "amount", "region"}
    assert out.frame.count() == 3


@pytest.mark.asyncio
async def test_source_runs_sql_query(_spark_session) -> None:
    with Tapestry() as t:
        SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS id, 'EU' AS region",
            _config=KnotConfig(id="src"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["src"]
    rows = out.frame.collect()
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["region"] == "EU"


def test_construct_rejects_missing_session(_spark_session) -> None:
    with Tapestry():
        with pytest.raises(TypeError, match="spark_session"):
            SparkSource(
                spark_session=None,
                path="/tmp/x.parquet",
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_path_and_query(_spark_session) -> None:
    with Tapestry():
        with pytest.raises(TypeError, match="mutually exclusive"):
            SparkSource(
                spark_session=_spark_session,
                path="/tmp/x.parquet",
                query="SELECT 1",
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_neither_path_nor_query(_spark_session) -> None:
    with Tapestry():
        with pytest.raises(TypeError, match="either path"):
            SparkSource(
                spark_session=_spark_session,
                _config=KnotConfig(id="bad"),
            )
