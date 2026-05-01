"""Tests for :class:`PolarsCast`."""

from __future__ import annotations

import polars as pl
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_cast import PolarsCast
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_string_columns() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame({"id": ["1", "2"], "amount": ["12.5", "99.0"]})
    )


@pytest.mark.asyncio
class TestPolarsCast:
    async def test_python_primitives_are_translated_to_polars_dtypes(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PolarsCast(
                batch=batch,
                casts={"id": int, "amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["casted"]
        assert out.frame["id"].dtype == pl.Int64
        assert out.frame["amount"].dtype == pl.Float64

    async def test_polars_dtype_passes_through(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PolarsCast(
                batch=batch,
                casts={"id": pl.Int32},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["casted"]
        assert out.frame["id"].dtype == pl.Int32

    async def test_columns_not_in_frame_are_skipped(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PolarsCast(
                batch=batch,
                casts={"absent": int},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["casted"]
        # No-op; original dtypes preserved.
        assert out.frame["id"].dtype == pl.Utf8


class TestConstruction:
    def test_rejects_unknown_dtype_kind(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="Polars dtype"):
                PolarsCast(
                    batch=batch,
                    casts={"a": "int"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="c"),
                )
