"""``SchemaValidator`` — assesses whether a :class:`DataBatch` conforms to a
declared :class:`DataSchema`.

The validator is a :class:`Knot` subclass: it takes a batch parent and emits
a :class:`QualityReport`. It does not raise on a failed check — callers
compose a :class:`pirn.nodes.gate.gate.Gate` keyed on
``QualityReport.passed`` if they want the pipeline to halt::

    with Tapestry() as t:
        batch  = SomeSource(_config=KnotConfig(id="extract"))
        report = SchemaValidator(batch=batch, schema=expected,
                                 _config=KnotConfig(id="schema"))
        # halt on failure:
        Gate(input=report, predicate=lambda r: r.passed,
             _config=KnotConfig(id="schema_ok"))

This keeps the validator purely about *assessment*; *enforcement* is a
composition concern, decided per pipeline.

Algorithm:
    1. Validate that ``schema`` is a :class:`DataSchema` instance.
    2. For each ``(column, expected_type)`` pair declared in the schema:

       a. Scan all rows; count present, null, and type-mismatched values.
       b. Emit a ``column_presence`` / ``column_missing`` check — passes
          when every row contains the column.
       c. Emit a ``column_type`` check — passes when no non-null value has
          an unexpected type.
       d. If the column is not nullable, emit a ``column_null_unexpected``
          check — passes when no row carries a null value for it.

    3. Return a :class:`QualityReport` whose ``passed`` is the conjunction
       of all individual checks.

References:
    [1] Data quality dimensions — completeness, validity, integrity:
        Loshin, "The Practitioner's Guide to Data Quality Improvement"
        (Morgan Kaufmann, 2011), ch. 3.
    [2] :class:`pirn.domains.data.data_schema.DataSchema` — column type
        and nullability contract.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class SchemaValidator(Knot):
    """Validates that every row in a :class:`DataBatch` matches a
    :class:`DataSchema`."""

    def __init__(
        self,
        *,
        batch: Knot,
        schema: Knot | DataSchema,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, schema=schema, _config=_config, **kwargs)

    async def process(
        self,
        *,
        batch: DataBatch,
        schema: Any,
        **_: Any,
    ) -> QualityReport:
        if not isinstance(schema, DataSchema):
            raise TypeError(
                f"SchemaValidator: schema must be a DataSchema, got {type(schema).__name__}"
            )
        checks: list[QualityCheck] = []
        for column, expected_type in schema.columns.items():
            checks.extend(
                SchemaValidator._check_column(
                    batch, column, expected_type, schema.is_nullable(column)
                )
            )
        passed = all(c.passed for c in checks)
        return QualityReport(
            passed=passed,
            checks=tuple(checks),
            row_count=batch.row_count,
        )

    @staticmethod
    def _check_column(
        batch: DataBatch,
        column: str,
        expected_type: type,
        is_nullable: bool,
    ) -> list[QualityCheck]:
        present_count = 0
        null_count = 0
        type_errors = 0
        for row in batch.rows:
            if column not in row:
                continue
            present_count += 1
            value = row[column]
            if value is None:
                null_count += 1
                continue
            if not isinstance(value, expected_type):
                type_errors += 1

        results: list[QualityCheck] = []

        if present_count == batch.row_count:
            results.append(
                QualityCheck(
                    name="column_presence",
                    passed=True,
                    threshold=str(batch.row_count),
                    actual=str(present_count),
                    column=column,
                )
            )
        else:
            results.append(
                QualityCheck(
                    name="column_missing",
                    passed=False,
                    threshold=str(batch.row_count),
                    actual=str(present_count),
                    column=column,
                )
            )

        results.append(
            QualityCheck(
                name="column_type",
                passed=type_errors == 0,
                threshold=expected_type.__name__,
                actual=f"{type_errors} mismatches",
                column=column,
            )
        )

        if not is_nullable:
            results.append(
                QualityCheck(
                    name="column_null_unexpected",
                    passed=null_count == 0,
                    threshold="0",
                    actual=str(null_count),
                    column=column,
                )
            )

        return results
