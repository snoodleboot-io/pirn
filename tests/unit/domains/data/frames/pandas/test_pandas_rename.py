"""Tests for :class:`PandasRename`."""

from __future__ import annotations

import pandas as pd
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.frames.pandas.pandas_rename import PandasRename
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {"user_id": [1, 2], "user_name": ["alice", "bob"], "region": ["EU", "US"]}
        )
    )


@pytest.mark.asyncio
class TestPandasRename:
    async def test_renames_columns(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasRename(
                batch=batch,
                mapping={"user_id": "id", "user_name": "name"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["renamed"]
        assert set(out.column_names) == {"id", "name", "region"}

    async def test_unknown_columns_are_silently_ignored(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasRename(
                batch=batch,
                mapping={"user_id": "id", "absent": "x"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["renamed"]
        assert "id" in out.column_names
        assert "x" not in out.column_names


class TestConstruction:
    def test_rejects_empty_mapping(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="non-empty"):
                PandasRename(batch=batch, mapping={}, _config=KnotConfig(id="r"))
