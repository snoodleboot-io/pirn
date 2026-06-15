"""Tests for :class:`PanderaPandasValidator`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd

try:
    import pandera.pandas as pa
except ImportError as _e:
    raise unittest.SkipTest("pandera.pandas not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn_data.quality_report import QualityReport
from pirn_data.validation.pandera.pandera_pandas_validator import (
    PanderaPandasValidator,
)


class _UsersModel(pa.DataFrameModel):
    id: int = pa.Field(gt=0)
    name: str = pa.Field(str_length={"min_value": 1})


def _valid_batch_factory():
    @knot
    async def emit() -> PandasDataBatch:
        return PandasDataBatch(
            frame=pd.DataFrame({"id": [1, 2, 3], "name": ["alice", "bob", "carol"]})
        )
    return emit


def _invalid_batch_factory():
    @knot
    async def emit() -> PandasDataBatch:
        return PandasDataBatch(
            frame=pd.DataFrame(
                {"id": [1, 2, -3, 4], "name": ["alice", "", "carol", "dave"]}
            )
        )
    return emit


def _make_batch() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame({"id": [1, 2], "name": ["alice", "bob"]})
    )


class TestPanderaPandasValidator(unittest.IsolatedAsyncioTestCase):
    async def test_passing_report_for_valid_frame_against_dataframe_model(self) -> None:
        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            PanderaPandasValidator(
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
            PanderaPandasValidator(
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
            PanderaPandasValidator(
                batch=batch, schema=schema,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_schema_from_upstream_knot(self) -> None:
        @knot
        async def emit_schema() -> object:
            return _UsersModel

        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            schema_knot = emit_schema(_config=KnotConfig(id="schema"))
            PanderaPandasValidator(
                batch=batch,
                schema=schema_knot,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self) -> PanderaPandasValidator:
        @knot
        async def upstream() -> PandasDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return PanderaPandasValidator(
                batch=batch,
                schema=_UsersModel,
                _config=KnotConfig(id="v"),
            )

    async def test_rejects_non_pandera_schema(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "DataFrameModel"):
            await k.process(batch=_make_batch(), schema={"id": int})

    async def test_rejects_none_schema(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "DataFrameModel"):
            await k.process(batch=_make_batch(), schema=None)
