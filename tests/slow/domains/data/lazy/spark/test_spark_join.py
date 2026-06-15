"""Tests for :class:`SparkJoin`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn_data.lazy.spark.spark_join import SparkJoin
from pirn_data.lazy.spark.spark_source import SparkSource


def _orders_query() -> str:
    return (
        "SELECT * FROM VALUES "
        "(1, 'EU'), (2, 'EU'), (3, 'US') "
        "AS t(order_id, region)"
    )


def _regions_query() -> str:
    return (
        "SELECT * FROM VALUES "
        "('EU', 'Europe'), ('US', 'United States') "
        "AS t(region, region_name)"
    )


@pytest.mark.asyncio
async def test_inner_join_on_shared_column(_spark_session) -> None:
    with Tapestry() as t:
        orders = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="orders"),
        )
        regions = SparkSource(
            spark_session=_spark_session,
            query=_regions_query(),
            _config=KnotConfig(id="regions"),
        )
        SparkJoin(
            left=orders,
            right=regions,
            on="region",
            how="inner",
            _config=KnotConfig(id="joined"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["joined"]
    rows = out.frame.collect()
    assert len(rows) == 3
    assert {row["region_name"] for row in rows} == {"Europe", "United States"}


@pytest.mark.asyncio
async def test_left_right_on_join(_spark_session) -> None:
    with Tapestry() as t:
        orders = SparkSource(
            spark_session=_spark_session,
            query=(
                "SELECT * FROM VALUES (1, 'EU'), (2, 'US') "
                "AS t(order_id, ord_region)"
            ),
            _config=KnotConfig(id="orders"),
        )
        regions = SparkSource(
            spark_session=_spark_session,
            query=(
                "SELECT * FROM VALUES ('EU', 'Europe'), ('US', 'States') "
                "AS t(reg_region, name)"
            ),
            _config=KnotConfig(id="regions"),
        )
        SparkJoin(
            left=orders,
            right=regions,
            left_on="ord_region",
            right_on="reg_region",
            how="inner",
            _config=KnotConfig(id="joined"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["joined"]
    rows = out.frame.collect()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_cross_join(_spark_session) -> None:
    with Tapestry() as t:
        a = SparkSource(
            spark_session=_spark_session,
            query="SELECT * FROM VALUES (1), (2) AS t(x)",
            _config=KnotConfig(id="a"),
        )
        b = SparkSource(
            spark_session=_spark_session,
            query="SELECT * FROM VALUES ('a'), ('b') AS t(y)",
            _config=KnotConfig(id="b"),
        )
        SparkJoin(
            left=a,
            right=b,
            how="cross",
            _config=KnotConfig(id="cross"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["cross"]
    rows = out.frame.collect()
    assert len(rows) == 4


def test_construct_rejects_unknown_how(_spark_session) -> None:
    with Tapestry():
        a = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="a"),
        )
        b = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="b"),
        )
        with pytest.raises(ValueError, match="how must be one of"):
            SparkJoin(
                left=a,
                right=b,
                on="x",
                how="full-outer",
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_on_with_left_right_on(_spark_session) -> None:
    with Tapestry():
        a = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="a"),
        )
        b = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="b"),
        )
        with pytest.raises(TypeError, match="mutually exclusive"):
            SparkJoin(
                left=a,
                right=b,
                on="x",
                left_on="x",
                right_on="x",
                _config=KnotConfig(id="bad"),
            )


def test_construct_rejects_invalid_column_name(_spark_session) -> None:
    with Tapestry():
        a = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="a"),
        )
        b = SparkSource(
            spark_session=_spark_session,
            query="SELECT 1 AS x",
            _config=KnotConfig(id="b"),
        )
        with pytest.raises(ValueError, match="not a plain identifier"):
            SparkJoin(
                left=a,
                right=b,
                on="x; DROP TABLE",
                _config=KnotConfig(id="bad"),
            )
