"""Tests for :class:`SparkFilter`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
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
async def test_filter_keeps_frame_deferred(_spark_session) -> None:
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        SparkFilter(
            frame=src,
            predicate="region = 'EU'",
            _config=KnotConfig(id="eu"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["eu"]
    assert isinstance(out, SparkDataFrame)
    rows = out.frame.collect()
    assert len(rows) == 3
    assert {row["region"] for row in rows} == {"EU"}


@pytest.mark.asyncio
async def test_filter_chains(_spark_session) -> None:
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
        SparkFilter(
            frame=eu,
            predicate="amount > 5.0",
            _config=KnotConfig(id="big_eu"),
        )
    result = await t.run(RunRequest())
    out: SparkDataFrame = result.outputs["big_eu"]
    rows = out.frame.collect()
    assert len(rows) == 2  # ids 1, 2


def test_construct_rejects_non_string_predicate(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(TypeError, match="string"):
            SparkFilter(
                frame=src,
                predicate=lambda f: f.region == "EU",  # type: ignore[arg-type]
                _config=KnotConfig(id="f"),
            )


def test_construct_rejects_empty_predicate(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="non-empty"):
            SparkFilter(
                frame=src,
                predicate="   ",
                _config=KnotConfig(id="f"),
            )
