"""``NullRateGate`` — assesses per-column null rates against caller-supplied
thresholds.

Each entry in ``thresholds`` is the maximum allowed null rate for the
column (a float in ``[0.0, 1.0]``). A column whose observed null rate
exceeds its threshold contributes a failed :class:`QualityCheck`. Columns
not in ``thresholds`` are not assessed.

Wrap with :class:`pirn.nodes.gate.gate.Gate` to halt the pipeline on
failure (see :class:`SchemaValidator` docstring for the standard pattern).
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class NullRateGate(Knot):
    """Reports per-column null rates against configured thresholds."""

    def __init__(
        self,
        *,
        batch: Knot,
        thresholds: Mapping[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(thresholds, Mapping) or not thresholds:
            raise TypeError(
                "NullRateGate: thresholds must be a non-empty mapping of "
                "column name to maximum allowed null rate"
            )
        for column, rate in thresholds.items():
            if not isinstance(rate, (int, float)):
                raise TypeError(
                    f"NullRateGate: threshold for {column!r} must be a number, "
                    f"got {type(rate).__name__}"
                )
            if not 0.0 <= float(rate) <= 1.0:
                raise ValueError(
                    f"NullRateGate: threshold for {column!r} must be in [0.0, 1.0], "
                    f"got {rate!r}"
                )
        self._thresholds: dict[str, float] = {k: float(v) for k, v in thresholds.items()}
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def thresholds(self) -> Mapping[str, float]:
        return dict(self._thresholds)

    async def process(self, batch: DataBatch, **_: Any) -> QualityReport:
        """Assess each column's null rate against its threshold and return a QualityReport.

        Args:
            batch: The DataBatch whose column null rates will be measured.

        Returns:
            A QualityReport with one check per configured column, passing when the
            observed null rate does not exceed the column's threshold.
        """
        row_count = batch.row_count
        checks: list[QualityCheck] = []

        for column, threshold in self._thresholds.items():
            actual_rate = self._null_rate(batch, column, row_count)
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

    def _null_rate(
        self, batch: DataBatch, column: str, row_count: int
    ) -> float:
        if row_count == 0:
            return 0.0
        null_count = sum(
            1 for row in batch.rows
            if column not in row or row[column] is None
        )
        return null_count / row_count
