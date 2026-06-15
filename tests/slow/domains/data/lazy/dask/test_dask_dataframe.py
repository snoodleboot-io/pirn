"""Tests for :class:`DaskDataFrame`."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from datetime import UTC

import dask.dataframe as dd
import pandas as pd
from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame


def _orders_frame() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {
            "id":     [1, 2, 3, 4],
            "amount": [10.0, 25.0, 5.0, 100.0],
            "region": ["EU", "EU", "EU", "US"],
        }
    )
    return dd.from_pandas(pdf, npartitions=2)


class TestDaskDataFrame:
    def test_column_names_from_frame(self) -> None:
        batch = DaskDataFrame(frame=_orders_frame(), backend_name="dask")
        assert set(batch.column_names) == {"id", "amount", "region"}

    def test_default_fetched_at_is_utc(self) -> None:
        batch = DaskDataFrame(frame=_orders_frame())
        assert batch.fetched_at.tzinfo is UTC

    def test_npartitions_property(self) -> None:
        batch = DaskDataFrame(frame=_orders_frame())
        assert batch.npartitions == 2

    def test_with_frame_preserves_metadata(self) -> None:
        original = DaskDataFrame(
            frame=_orders_frame(),
            backend_name="dask",
            source_uri="memory://orders",
        )
        replaced = original.with_frame(original.frame[original.frame.id > 1])
        assert replaced.backend_name == "dask"
        assert replaced.source_uri == "memory://orders"
        assert replaced.fetched_at == original.fetched_at
