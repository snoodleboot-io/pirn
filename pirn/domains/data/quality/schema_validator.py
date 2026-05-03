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
        schema: DataSchema,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(schema, DataSchema):
            raise TypeError(
                "SchemaValidator: schema must be a DataSchema, "
                f"got {type(schema).__name__}"
            )
        self._schema = schema
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def schema(self) -> DataSchema:
        return self._schema

    async def process(self, batch: DataBatch, **_: Any) -> QualityReport:
        """Validate each batch row against the declared schema and return a QualityReport.

        Args:
            batch: The DataBatch to validate against the configured schema.

        Returns:
            A QualityReport with presence, type, and nullability checks for each
            declared schema column.
        """
        checks: list[QualityCheck] = []
        for column, expected_type in self._schema.columns.items():
            checks.extend(self._check_column(batch, column, expected_type))
        passed = all(c.passed for c in checks)
        return QualityReport(
            passed=passed,
            checks=tuple(checks),
            row_count=batch.row_count,
        )

    def _check_column(
        self,
        batch: DataBatch,
        column: str,
        expected_type: type,
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

        is_nullable = self._schema.is_nullable(column)
        results: list[QualityCheck] = []

        results.append(
            QualityCheck(
                name="column_presence",
                passed=present_count == batch.row_count,
                threshold=str(batch.row_count),
                actual=str(present_count),
                column=column,
                # Reuse the standard name keyword "missing" so callers
                # / tests can identify presence failures uniformly.
            ) if present_count == batch.row_count
            else QualityCheck(
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
