"""``PanderaPandasValidator`` — bridge between Pandera schemas and pirn's
:class:`QualityReport`.

Takes a Tier-2 :class:`PandasDataBatch` and validates it against a
``pandera.pandas`` schema (``DataFrameModel`` subclass or
``DataFrameSchema`` instance). Validation runs in *lazy* mode, so every
failed check is collected — the caller doesn't lose visibility on later
problems just because an early one fired.

Failures are translated into one :class:`QualityCheck` per row of
Pandera's ``failure_cases`` table, then bundled into a
:class:`QualityReport`. Same downstream shape as the rest of pirn's
quality knots — compose with :class:`pirn.nodes.gate.gate.Gate` keyed on
``QualityReport.passed`` to halt the pipeline on validation failure.

Mirrors
:class:`pirn.domains.data.validation.pandera.pandera_polars_validator.PanderaPolarsValidator`
but targets the original Pandas-flavoured pandera API (``pandera.pandas``,
which predates ``pandera.polars`` and is the canonical pandera surface).

Algorithm:
    1. In ``process()``, verify that ``schema`` is either a
       ``pandera.pandas.DataFrameModel`` subclass or a
       ``pandera.pandas.DataFrameSchema`` instance. Raise ``TypeError``
       if neither.
    2. Call ``schema.validate(batch.frame, lazy=True)``. Lazy mode collects
       all failures rather than stopping at the first one.
    3. If validation succeeds (no exception), emit a passing
       :class:`QualityReport`.
    4. On ``SchemaErrors``, translate each row of ``exc.failure_cases``
       into a :class:`QualityCheck` and emit a failing
       :class:`QualityReport`.

    ```text
    try:
        schema.validate(frame, lazy=True)
        return QualityReport(passed=True)
    except SchemaErrors as exc:
        return QualityReport(passed=False,
                             checks=failure_cases_to_checks(exc))
    ```

References:
    [1] Pandera — lazy validation and SchemaErrors:
        https://pandera.readthedocs.io/en/stable/lazy_validation.html
    [2] Pandera — DataFrameModel (model-based schema API):
        https://pandera.readthedocs.io/en/stable/dataframe_models.html
    [3] Pandera — DataFrameSchema (object-based schema API):
        https://pandera.readthedocs.io/en/stable/dataframe_schemas.html
    [4] Alternative: Great Expectations (chosen Pandera here for its
        tighter pandas/polars integration and richer column-level check
        vocabulary; see GreatExpectationsPandasValidator for the GE
        counterpart):
        https://docs.greatexpectations.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class PanderaPandasValidator(Knot):
    """Validate a :class:`PandasDataBatch` against a Pandera Pandas schema."""

    def __init__(
        self,
        *,
        batch: Knot,
        schema: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, schema=schema, _config=_config, **kwargs)

    async def process(
        self,
        batch: PandasDataBatch,
        schema: Any,
        **_: Any,
    ) -> QualityReport:
        """Validate the PandasDataBatch against the Pandera schema in lazy mode.

        Args:
            batch: The PandasDataBatch to validate.
            schema: A ``pandera.pandas.DataFrameModel`` subclass or
                ``pandera.pandas.DataFrameSchema`` instance.

        Returns:
            A QualityReport with one failed QualityCheck per Pandera failure case,
            or a passing report when the schema is satisfied.
        """
        if not self._is_pandera_schema(schema):
            raise TypeError(
                "PanderaPandasValidator: schema must be a "
                "pandera.pandas DataFrameModel subclass or a "
                "DataFrameSchema instance"
            )
        from pandera.errors import SchemaErrors

        try:
            schema.validate(batch.frame, lazy=True)
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
            import pandera.pandas as pa
        except ImportError:
            return False
        if isinstance(candidate, type):
            return issubclass(candidate, pa.DataFrameModel)
        return isinstance(candidate, pa.DataFrameSchema)

    @staticmethod
    def _failures_to_checks(exc: Any) -> tuple[QualityCheck, ...]:
        """Translate Pandera's ``failure_cases`` table into pirn checks.

        ``failure_cases`` is a pandas DataFrame with columns ``column``,
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
