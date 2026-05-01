"""Tests for :class:`PolarsWindowCalc`."""

from __future__ import annotations

import polars as pl
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_window_calc import PolarsWindowCalc
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "region": ["EU", "EU", "EU", "US", "US"],
                "amount": [10.0, 25.0, 5.0,  100.0, 50.0],
            }
        )
    )


@pytest.mark.asyncio
class TestPolarsWindowCalc:
    async def test_partitioned_rank(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsWindowCalc(
                batch=batch,
                windows=(
                    pl.col("amount")
                    .rank(method="ordinal", descending=True)
                    .over("region")
                    .alias("rank_in_region"),
                ),
                _config=KnotConfig(id="ranked"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["ranked"]
        assert "rank_in_region" in out.column_names
        # Largest EU amount (25.0) ranks 1; largest US amount (100.0) ranks 1.
        eu_rows = out.frame.filter(pl.col("region") == "EU").sort("amount")
        assert eu_rows["rank_in_region"].to_list() == [3, 2, 1]

    async def test_cumulative_sum(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PolarsWindowCalc(
                batch=batch,
                windows=(pl.col("amount").cum_sum().alias("running_total"),),
                _config=KnotConfig(id="cum"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["cum"]
        assert out.frame["running_total"].to_list() == [
            10.0, 35.0, 40.0, 140.0, 190.0,
        ]


class TestConstruction:
    def test_rejects_empty_windows(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                PolarsWindowCalc(
                    batch=batch, windows=(),
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_non_expr(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="polars.Expr"):
                PolarsWindowCalc(
                    batch=batch,
                    windows=("rank()",),  # type: ignore[arg-type]
                    _config=KnotConfig(id="w"),
                )
