"""``RowCountCheck`` — assesses whether a :class:`DataBatch`'s row count
falls within ``[min_rows, max_rows]``.

Despite the legacy "Gate" suffix in the catalog, this is a :class:`Knot`
that emits a :class:`QualityReport`. Wrap with
:class:`pirn.nodes.gate.gate.Gate` to halt the pipeline on failure::

    report = RowCountCheck(batch=extract, min_rows=1, max_rows=1_000_000,
                          _config=KnotConfig(id="rowcount"))
    Gate(input=report, predicate=lambda r: r.passed,
         _config=KnotConfig(id="rowcount_ok"))

Algorithm:
    1. Validate ``min_rows >= 0`` and, when set, ``max_rows >= min_rows``.
    2. Read ``N = batch.row_count``.
    3. Emit a ``row_count_min`` check: ``passed = (N >= min_rows)``.
    4. If ``max_rows`` is set, emit a ``row_count_max`` check:
       ``passed = (N <= max_rows)``.
    5. Return a :class:`QualityReport` whose ``passed`` is the conjunction
       of all emitted checks.

Math:
    Let :math:`N = \\text{batch.row\\_count}`:

    $$
    \\text{passed} = (N \\geq \\text{min\\_rows}) \\;\\wedge\\;
        (\\text{max\\_rows} = \\text{None} \\;\\vee\\; N \\leq \\text{max\\_rows})
    $$

References:
    [1] :class:`pirn.domains.data.data_batch.DataBatch` — ``row_count``
        property.
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
        min_rows: Knot | int = 0,
        max_rows: Knot | int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            min_rows=min_rows,
            max_rows=max_rows,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        batch: DataBatch,
        min_rows: int = 0,
        max_rows: int | None = None,
        **_: Any,
    ) -> QualityReport:
        if min_rows < 0:
            raise ValueError("RowCountCheck: min_rows must be >= 0")
        if max_rows is not None and max_rows < min_rows:
            raise ValueError("RowCountCheck: max_rows must be >= min_rows when set")

        row_count = batch.row_count

        min_check = QualityCheck(
            name="row_count_min",
            passed=row_count >= min_rows,
            threshold=str(min_rows),
            actual=str(row_count),
        )
        checks: list[QualityCheck] = [min_check]

        if max_rows is not None:
            max_check = QualityCheck(
                name="row_count_max",
                passed=row_count <= max_rows,
                threshold=str(max_rows),
                actual=str(row_count),
            )
            checks.append(max_check)

        passed = all(c.passed for c in checks)
        return QualityReport(
            passed=passed,
            checks=tuple(checks),
            row_count=row_count,
        )
