"""Tests for :class:`PanderaPolarsValidator`."""

from __future__ import annotations

import polars as pl
import pytest

pa = pytest.importorskip("pandera.polars")

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.quality_report import QualityReport
from pirn.domains.data.validation.pandera.pandera_polars_validator import (
    PanderaPolarsValidator,
)
from pirn.tapestry import Tapestry


class _UsersModel(pa.DataFrameModel):
    id: int = pa.Field(gt=0)
    name: str = pa.Field(str_length={"min_value": 1})


def _valid_batch_factory():
    @knot
    async def emit() -> PolarsDataBatch:
        return PolarsDataBatch(
            frame=pl.DataFrame({"id": [1, 2, 3], "name": ["alice", "bob", "carol"]})
        )
    return emit


def _invalid_batch_factory():
    @knot
    async def emit() -> PolarsDataBatch:
        return PolarsDataBatch(
            frame=pl.DataFrame(
                {"id": [1, 2, -3, 4], "name": ["alice", "", "carol", "dave"]}
            )
        )
    return emit


@pytest.mark.asyncio
class TestPanderaPolarsValidator:
    async def test_passing_report_for_valid_frame_against_dataframe_model(self) -> None:
        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            PanderaPolarsValidator(
                batch=batch, schema=_UsersModel,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True
        assert report.row_count == 3

    async def test_failing_report_lists_one_check_per_pandera_failure(self) -> None:
        with Tapestry() as t:
            batch = _invalid_batch_factory()(_config=KnotConfig(id="users"))
            PanderaPolarsValidator(
                batch=batch, schema=_UsersModel,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is False
        # Two failures: id=-3 (>0 violation) and name="" (str_length violation).
        assert len(report.failed_checks) == 2
        columns_failing = {c.column for c in report.failed_checks}
        assert columns_failing == {"id", "name"}

    async def test_dataframe_schema_instance_also_accepted(self) -> None:
        schema = pa.DataFrameSchema(
            {
                "id":   pa.Column(int, pa.Check.gt(0)),
                "name": pa.Column(str, pa.Check.str_length(min_value=1)),
            }
        )
        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            PanderaPolarsValidator(
                batch=batch, schema=schema,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True


class TestConstruction:
    def test_rejects_non_pandera_schema(self) -> None:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="DataFrameModel"):
                PanderaPolarsValidator(
                    batch=batch,
                    schema={"id": int},  # type: ignore[arg-type]
                    _config=KnotConfig(id="v"),
                )
