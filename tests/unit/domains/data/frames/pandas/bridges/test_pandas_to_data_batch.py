"""Tests for :class:`PandasToDataBatch`."""

from __future__ import annotations

import pandas as pd
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.bridges.pandas_to_data_batch import (
    PandasToDataBatch,
)
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_pandas_batch() -> PandasDataBatch:
    frame = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    return PandasDataBatch(frame=frame, source_uri="memory://x")


@pytest.mark.asyncio
class TestPandasToDataBatch:
    async def test_materialises_rows_as_dicts(self) -> None:
        with Tapestry() as t:
            batch = emit_pandas_batch(_config=KnotConfig(id="pandas"))
            PandasToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.row_count == 3
        assert out.rows == (
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
            {"id": 3, "name": "c"},
        )

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_pandas_batch(_config=KnotConfig(id="pandas"))
            PandasToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.source_uri == "memory://x"
