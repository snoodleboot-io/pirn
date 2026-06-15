"""``FreshnessCheck`` — assesses whether the most-recent timestamp in a
:class:`DataBatch` is no older than ``max_age``.

Useful as an SLA guard: incremental ETLs that haven't seen a row in N
hours often indicate an upstream outage. Wrap with
:class:`pirn.nodes.gate.gate.Gate` to halt the pipeline when freshness is
violated.

Notes:
- The timestamp column must contain :class:`datetime.datetime` values
  (timezone-aware preferred). Naive datetimes are treated as UTC.
- ``max_age`` is a :class:`datetime.timedelta`. Common helper:
  ``timedelta(hours=24)``.
- Empty batches and rows missing the timestamp column are reported as
  failed checks — silence is not freshness.

Algorithm:
    1. Iterate ``batch.rows``; for each row that contains ``column`` with a
       ``datetime`` value, normalise to UTC (if naive) and track the maximum.
    2. If no datetime was found, emit a ``freshness_no_timestamp`` check
       with ``passed=False``.
    3. Otherwise compute ``age = now_utc - newest``.
    4. Emit a ``freshness_max_age`` check with ``passed = (age <= max_age)``.
    5. Return a :class:`QualityReport` wrapping that single check.

Math:
    Let :math:`T` be the set of datetime values found in ``column`` across all rows:

    $$
    \\text{newest} = \\max_{t \\in T}\\, t
    $$

    $$
    \\text{age} = \\text{now}_{\\text{UTC}} - \\text{newest}
    $$

    $$
    \\text{passed} = \\text{age} \\leq \\text{max\\_age}
    $$

    When :math:`T` is empty (no datetime values found), ``passed = False``.

References:
    [1] Python ``datetime.timedelta`` —
        https://docs.python.org/3/library/datetime.html#timedelta-objects
    [2] UTC normalisation — naive datetimes replaced with ``tzinfo=UTC``
        following ISO 8601 convention.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_batch import DataBatch
from pirn_data.quality_check import QualityCheck
from pirn_data.quality_report import QualityReport


class FreshnessCheck(Knot):
    """Reports whether the newest value in ``column`` is within ``max_age``."""

    def __init__(
        self,
        *,
        batch: Knot,
        column: Knot | str,
        max_age: Knot | timedelta,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            column=column,
            max_age=max_age,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        batch: DataBatch,
        column: str,
        max_age: timedelta,
        **_: Any,
    ) -> QualityReport:
        if not isinstance(column, str) or not column:
            raise ValueError("FreshnessCheck: column must be a non-empty string")
        if not isinstance(max_age, timedelta):
            raise TypeError(
                "FreshnessCheck: max_age must be a datetime.timedelta, "
                f"got {type(max_age).__name__}"
            )
        if max_age.total_seconds() <= 0:
            raise ValueError("FreshnessCheck: max_age must be positive")

        now = datetime.now(UTC)
        newest = FreshnessCheck._newest_timestamp(batch, column)

        if newest is None:
            check = QualityCheck(
                name="freshness_no_timestamp",
                passed=False,
                threshold=str(max_age),
                actual="no timestamps",
                column=column,
            )
        else:
            age = now - newest
            check = QualityCheck(
                name="freshness_max_age",
                passed=age <= max_age,
                threshold=str(max_age),
                actual=str(age),
                column=column,
            )

        return QualityReport(
            passed=check.passed,
            checks=(check,),
            row_count=batch.row_count,
        )

    @staticmethod
    def _newest_timestamp(batch: DataBatch, column: str) -> datetime | None:
        newest: datetime | None = None
        for row in batch.rows:
            if column not in row:
                continue
            value = row[column]
            if not isinstance(value, datetime):
                continue
            normalised = value.replace(tzinfo=UTC) if value.tzinfo is None else value
            if newest is None or normalised > newest:
                newest = normalised
        return newest
