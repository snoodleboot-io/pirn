"""Tests for :class:`DataBatchToPandas`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.bridges.data_batch_to_pandas import (
    DataBatchToPandas,
)
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


def _upstream() -> Parameter:
    return Parameter("batch", DataBatch, _config=KnotConfig(id="up"))


class TestDataBatchToPandas(unittest.IsolatedAsyncioTestCase):
    async def test_constructs_pandas_frame_from_rows(self) -> None:
        knot = DataBatchToPandas(
            batch=_upstream(),
            _config=KnotConfig(id="pandas"),
        )
        batch = DataBatch(
            rows=({"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}),
            source_uri="memory://users",
        )
        result = await knot.process(batch=batch)
        assert isinstance(result, PandasDataBatch)
        assert result.row_count == 2
        assert set(result.column_names) == {"id", "name"}

    async def test_propagates_metadata(self) -> None:
        knot = DataBatchToPandas(
            batch=_upstream(),
            _config=KnotConfig(id="pandas"),
        )
        batch = DataBatch(
            rows=({"id": 1, "name": "alice"},),
            source_uri="memory://users",
        )
        result = await knot.process(batch=batch)
        assert result.source_uri == "memory://users"

    async def test_empty_batch_yields_empty_frame(self) -> None:
        knot = DataBatchToPandas(
            batch=_upstream(),
            _config=KnotConfig(id="pandas"),
        )
        result = await knot.process(batch=DataBatch())
        assert isinstance(result, PandasDataBatch)
        assert result.row_count == 0
