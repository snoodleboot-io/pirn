"""Tests for :class:`PolarsFilter`."""

from __future__ import annotations

import polars as pl
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_filter import PolarsFilter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


@pytest.mark.asyncio
class TestPolarsFilter:
    async def test_keeps_rows_matching_expression(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsFilter(
                batch=batch,
                expression=pl.col("active"),
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["active"]
        assert tuple(out.frame["id"].to_list()) == (1, 3)

    async def test_compound_expression(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PolarsFilter(
                batch=batch,
                expression=(pl.col("region") == "EU") & (pl.col("active")),
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["active_eu"]
        assert tuple(out.frame["id"].to_list()) == (1,)


class TestConstruction:
    def test_rejects_python_callable(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="polars.Expr"):
                PolarsFilter(
                    batch=batch,
                    expression=lambda r: True,  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )
