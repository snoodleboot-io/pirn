"""Tests for :class:`SparkCollectSink`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.spark.spark_collect_sink import SparkCollectSink
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
async def test_collect_returns_rows(_spark_session) -> None:
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
        SparkCollectSink(frame=eu, _config=KnotConfig(id="exec"))
    result = await t.run(RunRequest())
    rows = result.outputs["exec"]
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert all(row["region"] == "EU" for row in rows)


@pytest.mark.asyncio
async def test_collect_respects_max_rows(_spark_session) -> None:
    with Tapestry() as t:
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="src"),
        )
        SparkCollectSink(
            frame=src, max_rows=2, _config=KnotConfig(id="exec")
        )
    result = await t.run(RunRequest())
    matching = [e for e in result.exceptions if e.knot_id == "exec"]
    assert matching, "expected SparkCollectSink to record an exception"
    assert "max_rows" in matching[0].message


def test_construct_rejects_non_int_max_rows(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(TypeError, match="max_rows"):
            SparkCollectSink(
                frame=src,
                max_rows="ten",  # type: ignore[arg-type]
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_non_positive_max_rows(_spark_session) -> None:
    with Tapestry():
        src = SparkSource(
            spark_session=_spark_session,
            query=_orders_query(),
            _config=KnotConfig(id="s"),
        )
        with pytest.raises(ValueError, match="positive"):
            SparkCollectSink(
                frame=src,
                max_rows=0,
                _config=KnotConfig(id="x"),
            )
