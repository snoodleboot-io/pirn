"""Tests for :class:`GreatExpectationsPandasValidator`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd

try:
    import great_expectations as gx
except ImportError as _e:
    raise unittest.SkipTest("great_expectations not installed") from _e

from great_expectations.expectations import (
    ExpectColumnValuesToBeBetween,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToNotBeNull,
)
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn_data.quality_report import QualityReport
from pirn_data.validation.great_expectations.great_expectations_pandas_validator import (
    GreatExpectationsPandasValidator,
)


def _users_suite() -> gx.ExpectationSuite:
    """Suite with three column-level expectations covering id, name, role.

    GE 1.x requires an active data context to be present before suites
    can be assembled, even when the suite never gets persisted into the
    context. Calling ``get_context(mode="ephemeral")`` here primes the
    in-memory context that the SDK looks up internally.
    """
    gx.get_context(mode="ephemeral")
    suite = gx.ExpectationSuite(name="users_suite")
    suite.add_expectation(
        ExpectColumnValuesToBeBetween(column="id", min_value=1, max_value=1_000_000)
    )
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="name"))
    suite.add_expectation(
        ExpectColumnValuesToBeInSet(
            column="role", value_set=["admin", "member", "guest"]
        )
    )
    return suite


def _valid_batch_factory():
    @knot
    async def emit() -> PandasDataBatch:
        return PandasDataBatch(
            frame=pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "name": ["alice", "bob", "carol"],
                    "role": ["admin", "member", "guest"],
                }
            )
        )
    return emit


def _id_invalid_batch_factory():
    """Single failing column: id violates the >=1 lower bound."""
    @knot
    async def emit() -> PandasDataBatch:
        return PandasDataBatch(
            frame=pd.DataFrame(
                {
                    "id": [1, 2, -3, 4],
                    "name": ["alice", "bob", "carol", "dave"],
                    "role": ["admin", "member", "guest", "admin"],
                }
            )
        )
    return emit


def _multi_invalid_batch_factory():
    """Two failing columns: id (negative) and role (unknown value)."""
    @knot
    async def emit() -> PandasDataBatch:
        return PandasDataBatch(
            frame=pd.DataFrame(
                {
                    "id": [1, 2, -3],
                    "name": ["alice", "bob", "carol"],
                    "role": ["admin", "member", "wizard"],  # 'wizard' not in set
                }
            )
        )
    return emit


def _make_batch() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {"id": [1, 2], "name": ["alice", "bob"], "role": ["admin", "member"]}
        )
    )


class TestGreatExpectationsPandasValidator(unittest.IsolatedAsyncioTestCase):
    async def test_passing_report_for_valid_frame(self) -> None:
        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            GreatExpectationsPandasValidator(
                batch=batch,
                suite=_users_suite(),
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True
        assert report.row_count == 3
        assert report.failed_checks == ()

    async def test_failing_report_lists_one_check_per_failed_expectation(self,) -> None:
        with Tapestry() as t:
            batch = _id_invalid_batch_factory()(_config=KnotConfig(id="users"))
            GreatExpectationsPandasValidator(
                batch=batch,
                suite=_users_suite(),
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is False
        # Only the id-bounds expectation should fail; name + role pass.
        assert len(report.failed_checks) == 1
        check = report.failed_checks[0]
        assert check.column == "id"
        assert check.name == "expect_column_values_to_be_between"
        # Threshold is the JSON-serialised expectation kwargs minus 'column'.
        assert "min_value" in check.threshold and "max_value" in check.threshold
        # Actual surfaces the failing value(s).
        assert "-3" in check.actual

    async def test_multiple_columns_failing_emit_one_check_each(self) -> None:
        with Tapestry() as t:
            batch = _multi_invalid_batch_factory()(_config=KnotConfig(id="users"))
            GreatExpectationsPandasValidator(
                batch=batch,
                suite=_users_suite(),
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is False
        failed_columns = {c.column for c in report.failed_checks}
        assert failed_columns == {"id", "role"}
        # Both checks carry their expectation kind in `name`.
        names = {c.name for c in report.failed_checks}
        assert "expect_column_values_to_be_between" in names
        assert "expect_column_values_to_be_in_set" in names


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_suite_from_upstream_knot(self) -> None:
        suite = _users_suite()

        @knot
        async def emit_suite() -> object:
            return suite

        with Tapestry() as t:
            batch = _valid_batch_factory()(_config=KnotConfig(id="users"))
            suite_knot = emit_suite(_config=KnotConfig(id="suite"))
            GreatExpectationsPandasValidator(
                batch=batch,
                suite=suite_knot,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self) -> GreatExpectationsPandasValidator:
        suite = _users_suite()

        @knot
        async def upstream() -> PandasDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return GreatExpectationsPandasValidator(
                batch=batch,
                suite=suite,
                _config=KnotConfig(id="v"),
            )

    async def test_rejects_non_expectation_suite(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "ExpectationSuite"):
            await k.process(batch=_make_batch(), suite={"id": int})

    async def test_rejects_none_suite(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "ExpectationSuite"):
            await k.process(batch=_make_batch(), suite=None)
