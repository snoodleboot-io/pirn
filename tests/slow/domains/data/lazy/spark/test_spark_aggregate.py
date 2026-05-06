"""Tests for :class:`SparkAggregate`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.spark.spark_aggregate import SparkAggregate
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.domains.data.lazy.spark.spark_source import SparkSource
from pirn.tapestry import Tapestry


def _orders_query() -> str:
    return (
        "SELECT * FROM VALUES "
        "(1, 10.0, 'EU'), (2, 25.0, 'EU'), (3, 5.0, 'EU'), (4, 100.0, 'US') "
        "AS t(id, amount, region)"
    )


@pytest.mark.asyncio
async def test_aggregate_sum_by_region(_spark_session) -> None:
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        SparkAggregate(
            frame=src,
            by=("region",),
            aggs={"total": ("amount", "sum")},
            _config=KnotConfig(id="totals"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["totals"]
    rows = {row["region"]: row["total"] for row in out.frame.collect()}
    assert rows == {"EU": 40.0, "US": 100.0}


@pytest.mark.asyncio
async def test_aggregate_multiple_functions(_spark_session) -> None:
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        SparkAggregate(
            frame=src,
            by=("region",),
            aggs={
                "n":     ("id", "count"),
                "min_a": ("amount", "min"),
                "max_a": ("amount", "max"),
            },
            _config=KnotConfig(id="stats"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["stats"]
    rows = {row["region"]: row for row in out.frame.collect()}
    assert rows["EU"]["n"] == 3
    assert rows["EU"]["min_a"] == 5.0
    assert rows["EU"]["max_a"] == 25.0


def test_construct_rejects_unknown_fn(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="fn must be one of"):
            SparkAggregate(
                frame=src,
                by=("region",),
                aggs={"total": ("amount", "stddev")},
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_invalid_column_name(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="not a plain identifier"):
            SparkAggregate(
                frame=src,
                by=("region; DROP TABLE x",),
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_empty_by(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="non-empty"):
            SparkAggregate(
                frame=src,
                by=(),
                aggs={"total": ("amount", "sum")},
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_empty_aggs(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(TypeError, match="non-empty mapping"):
            SparkAggregate(
                frame=src,
                by=("region",),
                aggs={},
                _config=KnotConfig(id="bad"),
            )
