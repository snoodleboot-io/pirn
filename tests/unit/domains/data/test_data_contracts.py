"""Unit tests for the four data-domain contract dataclasses."""

from __future__ import annotations

from datetime import timezone

import pytest

from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


# ────────────────────────────────────────────────────────────── DataSchema


class TestDataSchema:
    def test_empty_schema_is_valid(self) -> None:
        s = DataSchema()
        assert s.column_names == ()
        assert s.primary_keys == ()

    def test_schema_with_columns(self) -> None:
        s = DataSchema(columns={"id": int, "name": str}, primary_keys=("id",))
        assert s.column_names == ("id", "name")

    def test_rejects_pk_not_in_columns(self) -> None:
        with pytest.raises(ValueError, match="unknown columns"):
            DataSchema(columns={"id": int}, primary_keys=("nope",))

    def test_rejects_nullable_not_in_columns(self) -> None:
        with pytest.raises(ValueError, match="unknown columns"):
            DataSchema(columns={"id": int}, nullable=("nope",))

    def test_is_nullable(self) -> None:
        s = DataSchema(columns={"id": int, "name": str}, nullable=("name",))
        assert s.is_nullable("name") is True
        assert s.is_nullable("id") is False

    def test_with_columns_merges(self) -> None:
        s = DataSchema(columns={"id": int})
        s2 = s.with_columns({"name": str})
        assert s2.column_names == ("id", "name")
        # Original is unchanged (frozen).
        assert s.column_names == ("id",)


# ─────────────────────────────────────────────────────────────── DataBatch


class TestDataBatch:
    def test_default_is_empty_with_utc_fetched_at(self) -> None:
        b = DataBatch()
        assert b.row_count == 0
        assert b.fetched_at.tzinfo is timezone.utc

    def test_with_rows_preserves_schema(self) -> None:
        schema = DataSchema(columns={"id": int})
        b = DataBatch(rows=(), schema=schema, source_uri="sqlite://x")
        b2 = b.with_rows(({"id": 1},))
        assert b2.row_count == 1
        assert b2.schema is schema
        assert b2.source_uri == "sqlite://x"

    def test_with_schema_preserves_rows(self) -> None:
        rows = ({"id": 1}, {"id": 2})
        b = DataBatch(rows=rows)
        new_schema = DataSchema(columns={"id": int})
        b2 = b.with_schema(new_schema)
        assert b2.rows == rows
        assert b2.schema is new_schema

    def test_dataclass_is_frozen(self) -> None:
        b = DataBatch()
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            b.rows = ({"id": 1},)  # type: ignore[misc]


# ─────────────────────────────────────────────────────── QualityCheck/Report


class TestQualityReport:
    def test_passing_report(self) -> None:
        checks = (
            QualityCheck(name="row_count_min", passed=True, threshold="1", actual="5"),
        )
        r = QualityReport(passed=True, checks=checks, row_count=5)
        assert r.failed_checks == ()

    def test_failing_check_with_passed_false(self) -> None:
        checks = (
            QualityCheck(
                name="row_count_min", passed=False, threshold="100", actual="5"
            ),
        )
        r = QualityReport(passed=False, checks=checks, row_count=5)
        assert len(r.failed_checks) == 1

    def test_inconsistency_raises(self) -> None:
        # passed=True but a check failed → invariant violated.
        checks = (
            QualityCheck(
                name="x", passed=False, threshold="100", actual="5"
            ),
        )
        with pytest.raises(ValueError, match="cannot be True"):
            QualityReport(passed=True, checks=checks)

    def test_default_sampled_at_is_utc(self) -> None:
        r = QualityReport(passed=True)
        assert r.sampled_at.tzinfo is timezone.utc
