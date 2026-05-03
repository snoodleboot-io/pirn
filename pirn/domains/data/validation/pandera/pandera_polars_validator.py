"""``PanderaPolarsValidator`` — bridge between Pandera schemas and pirn's
:class:`QualityReport`.

Takes a Tier-2 :class:`PolarsDataBatch` and validates it against a
``pandera.polars`` schema (``DataFrameModel`` subclass or
``DataFrameSchema`` instance). Validation runs in *lazy* mode, so every
failed check is collected — the caller doesn't lose visibility on later
problems just because an early one fired.

Failures are translated into one :class:`QualityCheck` per row of
Pandera's ``failure_cases`` table, then bundled into a
:class:`QualityReport`. Same downstream shape as the rest of pirn's
quality knots — compose with :class:`pirn.nodes.gate.gate.Gate` keyed on
``QualityReport.passed`` to halt the pipeline on validation failure.

Why a dedicated knot rather than wrapping Pandera schemas inside the
existing :class:`SchemaValidator`: Pandera's check vocabulary (string
length, numeric ranges, regex, custom checks, conditional checks,
multivariate checks) is far richer than the presence/type/null checks
the dict-based Tier-1 validator supports. Letting Pandera own the
validation while pirn owns the orchestration plays to each tool's
strengths.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class PanderaPolarsValidator(Knot):
    """Validate a :class:`PolarsDataBatch` against a Pandera Polars schema."""

    def __init__(
        self,
        *,
        batch: Knot,
        schema: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not self._is_pandera_schema(schema):
            raise TypeError(
                "PanderaPolarsValidator: schema must be a "
                "pandera.polars DataFrameModel subclass or a "
                "DataFrameSchema instance"
            )
        self._schema = schema
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def schema(self) -> Any:
        return self._schema

    async def process(self, batch: PolarsDataBatch, **_: Any) -> QualityReport:
        """Validate the PolarsDataBatch against the Pandera schema in lazy mode and return a QualityReport.

        Args:
            batch: The PolarsDataBatch to validate.

        Returns:
            A QualityReport with one failed QualityCheck per Pandera failure case,
            or a passing report when the schema is satisfied.
        """
        from pandera.errors import SchemaErrors

        try:
            self._schema.validate(batch.frame, lazy=True)
        except SchemaErrors as exc:
            return QualityReport(
                passed=False,
                checks=self._failures_to_checks(exc),
                row_count=batch.row_count,
            )
        return QualityReport(
            passed=True,
            checks=(),
            row_count=batch.row_count,
        )

    @staticmethod
    def _is_pandera_schema(candidate: Any) -> bool:
        """Recognise both ``DataFrameModel`` subclasses and ``DataFrameSchema`` instances.

        Done with duck typing so this module imports cleanly even when
        ``pandera`` is not installed (the actual call to
        :meth:`process` will fail at run time with a clearer error in
        that case).
        """
        try:
            import pandera.polars as pa
        except ImportError:
            return False
        if isinstance(candidate, type):
            return issubclass(candidate, pa.DataFrameModel)
        return isinstance(candidate, pa.DataFrameSchema)

    @staticmethod
    def _failures_to_checks(exc: Any) -> tuple[QualityCheck, ...]:
        """Translate Pandera's ``failure_cases`` table into pirn checks.

        ``failure_cases`` is a Polars DataFrame with columns ``column``,
        ``check``, ``failure_case``, and (sometimes) ``index``. One pirn
        :class:`QualityCheck` is emitted per failure row.
        """
        results: list[QualityCheck] = []
        cases = getattr(exc, "failure_cases", None)
        if cases is None:
            return tuple(results)
        # Support both pandas (legacy) and polars failure_cases tables.
        rows = cases.to_dicts() if hasattr(cases, "to_dicts") else cases.to_dict("records")
        for row in rows:
            results.append(
                QualityCheck(
                    name=str(row.get("check", "pandera_check")),
                    passed=False,
                    threshold=str(row.get("check", "")),
                    actual=str(row.get("failure_case", "")),
                    column=(
                        str(row["column"])
                        if row.get("column") is not None
                        else None
                    ),
                )
            )
        return tuple(results)
