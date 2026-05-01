"""Tests for :class:`SparkDataFrame`."""

from __future__ import annotations

from datetime import timezone

import pytest

pytestmark = pytest.mark.slow

from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


def _orders_frame():
    from pyspark.sql import SparkSession

    session = SparkSession.getActiveSession()
    assert session is not None
    return session.createDataFrame(
        [(1, 10.0, "EU"), (2, 25.0, "EU"), (3, 5.0, "EU"), (4, 100.0, "US")],
        ["id", "amount", "region"],
    )


class TestSparkDataFrame:
    def test_column_names_from_frame(self) -> None:
        batch = SparkDataFrame(frame=_orders_frame(), backend_name="spark")
        assert set(batch.column_names) == {"id", "amount", "region"}

    def test_default_fetched_at_is_utc(self) -> None:
        batch = SparkDataFrame(frame=_orders_frame())
        assert batch.fetched_at.tzinfo is timezone.utc

    def test_with_frame_preserves_metadata(self) -> None:
        original = SparkDataFrame(
            frame=_orders_frame(),
            backend_name="spark",
            source_uri="memory://orders",
        )
        replaced = original.with_frame(original.frame.filter("id > 1"))
        assert replaced.backend_name == "spark"
        assert replaced.source_uri == "memory://orders"
        assert replaced.fetched_at == original.fetched_at

    def test_dataframe_is_frozen(self) -> None:
        batch = SparkDataFrame(frame=_orders_frame())
        with pytest.raises(Exception):
            batch.backend_name = "other"  # type: ignore[misc]
