"""Tests for :class:`PandasCast`."""

from __future__ import annotations

import pandas as pd
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_cast import PandasCast
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_string_columns() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame({"id": ["1", "2"], "amount": ["12.5", "99.0"]})
    )


@pytest.mark.asyncio
class TestPandasCast:
    async def test_python_primitives_are_translated_to_pandas_dtypes(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"id": int, "amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        assert str(out.frame["id"].dtype) == "int64"
        assert str(out.frame["amount"].dtype) == "float64"

    async def test_dtype_string_passes_through(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"id": "int32"},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        assert str(out.frame["id"].dtype) == "int32"

    async def test_columns_not_in_frame_are_skipped(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"absent": int},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        # No-op; original dtypes preserved.
        assert out.frame["id"].dtype == object


class TestConstruction:
    def test_rejects_unknown_dtype_kind(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="Pandas dtype"):
                PandasCast(
                    batch=batch,
                    casts={"a": 123},  # type: ignore[dict-item]
                    _config=KnotConfig(id="c"),
                )
