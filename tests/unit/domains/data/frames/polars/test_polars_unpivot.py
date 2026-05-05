"""Tests for :class:`PolarsUnpivot`."""

from __future__ import annotations
import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_unpivot import PolarsUnpivot
from pirn.tapestry import Tapestry


@knot
async def emit_wide() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "user":   ["alice", "bob"],
                "clicks": [3, 7],
                "views":  [100, 200],
            }
        )
    )


class TestPolarsUnpivot(unittest.IsolatedAsyncioTestCase):
    async def test_long_reshape(self) -> None:
        with Tapestry() as t:
            batch = emit_wide(_config=KnotConfig(id="wide"))
            PolarsUnpivot(
                batch=batch,
                on=("clicks", "views"),
                index=("user",),
                variable_name="metric",
                value_name="value",
                _config=KnotConfig(id="long"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["long"]
        assert out.row_count == 4   # 2 users × 2 metrics
        assert set(out.column_names) == {"user", "metric", "value"}

    async def test_default_variable_and_value_names(self) -> None:
        with Tapestry() as t:
            batch = emit_wide(_config=KnotConfig(id="wide"))
            PolarsUnpivot(
                batch=batch,
                on=("clicks", "views"),
                index=("user",),
                _config=KnotConfig(id="long"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["long"]
        assert "variable" in out.column_names
        assert "value" in out.column_names


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_on(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                PolarsUnpivot(
                    batch=batch, on=(),
                    _config=KnotConfig(id="u"),
                )
