"""``FreshnessGate`` — assesses whether the most-recent timestamp in a
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
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


class FreshnessGate(Knot):
    """Reports whether the newest value in ``column`` is within ``max_age``."""

    def __init__(
        self,
        *,
        batch: Knot,
        column: str,
        max_age: timedelta,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(column, str) or not column:
            raise ValueError("FreshnessGate: column must be a non-empty string")
        if not isinstance(max_age, timedelta):
            raise TypeError(
                "FreshnessGate: max_age must be a datetime.timedelta, "
                f"got {type(max_age).__name__}"
            )
        if max_age.total_seconds() <= 0:
            raise ValueError("FreshnessGate: max_age must be positive")
        self._column = column
        self._max_age = max_age
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def column(self) -> str:
        return self._column

    @property
    def max_age(self) -> timedelta:
        return self._max_age

    async def process(self, batch: DataBatch, **_: Any) -> QualityReport:
        now = datetime.now(timezone.utc)
        newest = self._newest_timestamp(batch)

        if newest is None:
            check = QualityCheck(
                name="freshness_no_timestamp",
                passed=False,
                threshold=str(self._max_age),
                actual="no timestamps",
                column=self._column,
            )
        else:
            age = now - newest
            check = QualityCheck(
                name="freshness_max_age",
                passed=age <= self._max_age,
                threshold=str(self._max_age),
                actual=str(age),
                column=self._column,
            )

        return QualityReport(
            passed=check.passed,
            checks=(check,),
            row_count=batch.row_count,
        )

    def _newest_timestamp(self, batch: DataBatch) -> datetime | None:
        newest: datetime | None = None
        for row in batch.rows:
            if self._column not in row:
                continue
            value = row[self._column]
            if not isinstance(value, datetime):
                continue
            normalised = (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value
            )
            if newest is None or normalised > newest:
                newest = normalised
        return newest
