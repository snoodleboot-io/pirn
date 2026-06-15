"""``NullRateCheck`` — assesses per-column null rates against caller-supplied
thresholds.

Each entry in ``thresholds`` is the maximum allowed null rate for the
column (a float in ``[0.0, 1.0]``). A column whose observed null rate
exceeds its threshold contributes a failed :class:`QualityCheck`. Columns
not in ``thresholds`` are not assessed.

Wrap with :class:`pirn.nodes.gate.gate.Gate` to halt the pipeline on
failure (see :class:`SchemaValidator` docstring for the standard pattern).

Algorithm:
    1. Validate ``thresholds`` is a non-empty mapping of column → float in
       ``[0.0, 1.0]``.
    2. For each ``(column, threshold)`` pair, compute the null rate over
       ``batch.rows``.
    3. Emit one :class:`QualityCheck` per column with
       ``passed = (null_rate <= threshold)``.
    4. Return a :class:`QualityReport` whose ``passed`` flag is the
       conjunction of all per-column checks.

Math:
    Given :math:`N` rows and :math:`k_c` null or absent values for column :math:`c`:

    $$
    \\text{null\\_rate}(c) = \\begin{cases}
        k_c \\,/\\, N & N > 0 \\\\
        0.0          & N = 0
    \\end{cases}
    $$

    $$
    \\text{passed}(c) = \\text{null\\_rate}(c) \\leq \\text{threshold}(c)
    $$

    $$
    \\text{passed} = \\bigwedge_{c} \\text{passed}(c)
    $$

References:
    [1] Null rate / completeness — standard data quality dimension; see
        Loshin, "The Practitioner's Guide to Data Quality Improvement" (2011).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_batch import DataBatch
from pirn_data.quality_check import QualityCheck
from pirn_data.quality_report import QualityReport


class NullRateCheck(Knot):
    """Reports per-column null rates against configured thresholds."""

    def __init__(
        self,
        *,
        batch: Knot,
        thresholds: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            thresholds=thresholds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        batch: DataBatch,
        thresholds: Any,
        **_: Any,
    ) -> QualityReport:
        if not isinstance(thresholds, dict) or not thresholds:
            raise TypeError(
                "NullRateCheck: thresholds must be a non-empty mapping of "
                "column name to maximum allowed null rate"
            )
        for column, rate in thresholds.items():
            if not isinstance(rate, (int, float)):
                raise TypeError(
                    f"NullRateCheck: threshold for {column!r} must be a number, "
                    f"got {type(rate).__name__}"
                )
            if not 0.0 <= float(rate) <= 1.0:
                raise ValueError(
                    f"NullRateCheck: threshold for {column!r} must be in [0.0, 1.0], got {rate!r}"
                )

        normalised: dict[str, float] = {k: float(v) for k, v in thresholds.items()}
        row_count = batch.row_count
        checks: list[QualityCheck] = []

        for column, threshold in normalised.items():
            actual_rate = NullRateCheck._null_rate(batch, column, row_count)
            checks.append(
                QualityCheck(
                    name="null_rate",
                    passed=actual_rate <= threshold,
                    threshold=f"{threshold:.4f}",
                    actual=f"{actual_rate:.4f}",
                    column=column,
                )
            )

        passed = all(c.passed for c in checks)
        return QualityReport(
            passed=passed,
            checks=tuple(checks),
            row_count=row_count,
        )

    @staticmethod
    def _null_rate(batch: DataBatch, column: str, row_count: int) -> float:
        if row_count == 0:
            return 0.0
        null_count = sum(1 for row in batch.rows if column not in row or row[column] is None)
        return null_count / row_count
