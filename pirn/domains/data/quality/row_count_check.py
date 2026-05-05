"""``RowCountCheck`` — assesses whether a :class:`DataBatch`'s row count
falls within ``[min_rows, max_rows]``.

Despite the legacy "Gate" suffix in the catalog, this is a :class:`Knot`
that emits a :class:`QualityReport`. Wrap with
:class:`pirn.nodes.gate.gate.Gate` to halt the pipeline on failure::

    report = RowCountCheck(batch=extract, min_rows=1, max_rows=1_000_000,
                          _config=KnotConfig(id="rowcount"))
    Gate(input=report, predicate=lambda r: r.passed,
         _config=KnotConfig(id="rowcount_ok"))
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class RowCountCheck(Knot):
    """Reports whether the input batch's row count is within configured bounds."""

    def __init__(
        self,
        *,
        batch: Knot,
        min_rows: int = 0,
        max_rows: int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if min_rows < 0:
            raise ValueError("RowCountCheck: min_rows must be >= 0")
        if max_rows is not None and max_rows < min_rows:
            raise ValueError(
                "RowCountCheck: max_rows must be >= min_rows when set"
            )
        self._min_rows = min_rows
        self._max_rows = max_rows
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def min_rows(self) -> int:
        return self._min_rows

    @property
    def max_rows(self) -> int | None:
        return self._max_rows

    async def process(self, batch: DataBatch, **_: Any) -> QualityReport:
        """Check that the batch row count falls within the configured bounds and return a QualityReport.

        Args:
            batch: The DataBatch whose row count will be checked.

        Returns:
            A QualityReport with checks for the minimum and, if configured, maximum row count.
        """
        row_count = batch.row_count

        min_check = QualityCheck(
            name="row_count_min",
            passed=row_count >= self._min_rows,
            threshold=str(self._min_rows),
            actual=str(row_count),
        )
        checks: list[QualityCheck] = [min_check]

        if self._max_rows is not None:
            max_check = QualityCheck(
                name="row_count_max",
                passed=row_count <= self._max_rows,
                threshold=str(self._max_rows),
                actual=str(row_count),
            )
            checks.append(max_check)

        passed = all(c.passed for c in checks)
        return QualityReport(
            passed=passed,
            checks=tuple(checks),
            row_count=row_count,
        )
