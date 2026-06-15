"""Tests for :class:`pirn_data.quality.schema_validator.SchemaValidator`.

Each test composes the validator inside a real :class:`Tapestry` so we
prove the knot integrates with pirn's execution machinery. The validator
emits a :class:`QualityReport`; callers decide policy via
:class:`pirn.nodes.gate.gate.Gate` if they want to halt on failure.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema
from pirn_data.quality.schema_validator import SchemaValidator
from pirn_data.quality_report import QualityReport


@knot
async def emit_users() -> DataBatch:
    schema = DataSchema(columns={"id": int, "name": str}, primary_keys=("id",))
    rows = (
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
    )
    return DataBatch(rows=rows, schema=schema, source_uri="memory://users")


@knot
async def emit_users_missing_column() -> DataBatch:
    rows = ({"id": 1},)
    schema = DataSchema(columns={"id": int, "name": str})
    return DataBatch(rows=rows, schema=schema)


@knot
async def emit_users_wrong_type() -> DataBatch:
    rows = ({"id": "not-an-int", "name": "alice"},)
    schema = DataSchema(columns={"id": int, "name": str})
    return DataBatch(rows=rows, schema=schema)


@knot
async def emit_users_with_null() -> DataBatch:
    rows = ({"id": 1, "name": None},)
    schema = DataSchema(columns={"id": int, "name": str})
    return DataBatch(rows=rows, schema=schema)


@knot
async def emit_users_with_nullable_null() -> DataBatch:
    rows = ({"id": 1, "name": None},)
    schema = DataSchema(columns={"id": int, "name": str}, nullable=("name",))
    return DataBatch(rows=rows, schema=schema)


class TestSchemaValidatorPasses(unittest.IsolatedAsyncioTestCase):
    async def test_passing_report_when_every_row_conforms(self) -> None:
        expected_schema = DataSchema(
            columns={"id": int, "name": str}, primary_keys=("id",)
        )
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            SchemaValidator(
                batch=batch,
                schema=expected_schema,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: QualityReport = result.outputs["schema"]
        assert report.passed is True
        assert report.row_count == 2
        assert all(check.passed for check in report.checks)

    async def test_nullable_column_accepts_none(self) -> None:
        expected_schema = DataSchema(
            columns={"id": int, "name": str}, nullable=("name",)
        )
        with Tapestry() as t:
            batch = emit_users_with_nullable_null(_config=KnotConfig(id="users"))
            SchemaValidator(
                batch=batch,
                schema=expected_schema,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["schema"]
        assert report.passed is True


class TestSchemaValidatorFails(unittest.IsolatedAsyncioTestCase):
    async def test_missing_column_marks_check_failed(self) -> None:
        expected_schema = DataSchema(columns={"id": int, "name": str})
        with Tapestry() as t:
            batch = emit_users_missing_column(_config=KnotConfig(id="users"))
            SchemaValidator(
                batch=batch,
                schema=expected_schema,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["schema"]
        assert report.passed is False
        failed = report.failed_checks
        assert len(failed) == 1
        assert failed[0].column == "name"
        assert "missing" in failed[0].name.lower()

    async def test_wrong_type_marks_check_failed(self) -> None:
        expected_schema = DataSchema(columns={"id": int, "name": str})
        with Tapestry() as t:
            batch = emit_users_wrong_type(_config=KnotConfig(id="users"))
            SchemaValidator(
                batch=batch,
                schema=expected_schema,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["schema"]
        assert report.passed is False
        failed = report.failed_checks
        assert any(c.column == "id" and "type" in c.name.lower() for c in failed)

    async def test_unexpected_null_marks_check_failed(self) -> None:
        expected_schema = DataSchema(columns={"id": int, "name": str}, nullable=())
        with Tapestry() as t:
            batch = emit_users_with_null(_config=KnotConfig(id="users"))
            SchemaValidator(
                batch=batch,
                schema=expected_schema,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["schema"]
        assert report.passed is False
        failed = report.failed_checks
        assert any(c.column == "name" and "null" in c.name.lower() for c in failed)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_schema_from_upstream_knot(self) -> None:
        @knot
        async def emit_schema() -> DataSchema:
            return DataSchema(columns={"id": int, "name": str}, primary_keys=("id",))

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            schema_knot = emit_schema(_config=KnotConfig(id="schema_src"))
            SchemaValidator(
                batch=batch,
                schema=schema_knot,
                _config=KnotConfig(id="schema"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["schema"]
        assert report.passed is True


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> SchemaValidator:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        default_schema = DataSchema(columns={"id": int})
        kwargs.setdefault("schema", default_schema)
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return SchemaValidator(batch=batch, _config=KnotConfig(id="sv"), **kwargs)

    async def test_rejects_non_data_schema(self) -> None:
        k = self._make_knot(schema={"id": int})  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "DataSchema"):
            await k.process(batch=DataBatch(), schema={"id": int})
