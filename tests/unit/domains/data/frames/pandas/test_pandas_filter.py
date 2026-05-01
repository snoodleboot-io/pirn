"""Tests for :class:`PandasFilter`."""

from __future__ import annotations

import pandas as pd
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.frames.pandas.pandas_filter import PandasFilter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


@pytest.mark.asyncio
class TestPandasFilter:
    async def test_keeps_rows_matching_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasFilter(
                batch=batch,
                predicate=lambda df: df["active"],
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["active"]
        assert tuple(out.frame["id"].tolist()) == (1, 3)

    async def test_compound_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PandasFilter(
                batch=batch,
                predicate=lambda df: (df["region"] == "EU") & df["active"],
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["active_eu"]
        assert tuple(out.frame["id"].tolist()) == (1,)


class TestConstruction:
    def test_rejects_non_callable_predicate(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="callable"):
                PandasFilter(
                    batch=batch,
                    predicate="active == True",  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )
