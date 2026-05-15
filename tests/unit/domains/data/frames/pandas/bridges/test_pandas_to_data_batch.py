"""Tests for :class:`PandasToDataBatch`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.bridges.pandas_to_data_batch import (
    PandasToDataBatch,
)
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


def _upstream() -> Parameter:
    return Parameter("batch", PandasDataBatch, _config=KnotConfig(id="up"))


class TestPandasToDataBatch(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_rows_as_dicts(self) -> None:
        knot = PandasToDataBatch(
            batch=_upstream(),
            _config=KnotConfig(id="dict"),
        )
        frame = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        batch = PandasDataBatch(frame=frame, source_uri="memory://x")
        result = await knot.process(batch=batch)
        assert isinstance(result, DataBatch)
        assert result.row_count == 3
        assert result.rows == (
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
            {"id": 3, "name": "c"},
        )

    async def test_propagates_metadata(self) -> None:
        knot = PandasToDataBatch(
            batch=_upstream(),
            _config=KnotConfig(id="dict"),
        )
        frame = pd.DataFrame({"id": [1]})
        batch = PandasDataBatch(frame=frame, source_uri="memory://x")
        result = await knot.process(batch=batch)
        assert result.source_uri == "memory://x"
