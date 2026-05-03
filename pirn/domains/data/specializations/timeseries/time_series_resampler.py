"""``TimeSeriesResampler`` — resample time-series to a target frequency.

Rows are grouped into fixed-width time buckets of ``frequency_seconds``
and each group is collapsed using the configured aggregation function
(mean / sum / last / first).  The bucket timestamp is the floor of the
original timestamp.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class TimeSeriesResampler(Knot):
    """Collapse time-series rows into fixed-frequency buckets."""

    def __init__(
        self,
        *,
        rows: Knot,
        timestamp_column: str,
        value_column: str,
        frequency_seconds: float,
        aggregation: Literal["mean", "sum", "last", "first"] = "mean",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("value_column", value_column)
        if not isinstance(frequency_seconds, (int, float)) or frequency_seconds <= 0:
            raise ValueError(
                "TimeSeriesResampler: frequency_seconds must be a positive number"
            )
        if aggregation not in ("mean", "sum", "last", "first"):
            raise ValueError(
                "TimeSeriesResampler: aggregation must be mean/sum/last/first"
            )
        self._timestamp_column = timestamp_column
        self._value_column = value_column
        self._frequency = timedelta(seconds=frequency_seconds)
        self._aggregation = aggregation
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _floor(self, dt: datetime) -> datetime:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if dt.tzinfo is None:
            epoch = datetime(1970, 1, 1)
        freq_s = self._frequency.total_seconds()
        since = (dt - epoch).total_seconds()
        return epoch + timedelta(seconds=(since // freq_s) * freq_s)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Resample rows to the target frequency using the configured aggregation.

        Args:
            rows: Upstream rows; each must have ``timestamp_column`` (datetime or
                  ISO-8601 string) and ``value_column`` (numeric).

        Returns:
            One row per bucket with ``timestamp_column`` set to the bucket floor
            and ``value_column`` set to the aggregated value, sorted ascending.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        buckets: dict[datetime, list[Any]] = {}
        bucket_order: list[datetime] = []
        for row in rows:
            ts = _as_dt(row[self._timestamp_column])
            bucket = self._floor(ts)
            if bucket not in buckets:
                buckets[bucket] = []
                bucket_order.append(bucket)
            buckets[bucket].append(row[self._value_column])

        result: list[dict[str, Any]] = []
        for bucket in sorted(bucket_order):
            vals = buckets[bucket]
            if self._aggregation == "mean":
                agg = sum(vals) / len(vals)
            elif self._aggregation == "sum":
                agg = sum(vals)
            elif self._aggregation == "first":
                agg = vals[0]
            else:
                agg = vals[-1]
            result.append(
                {self._timestamp_column: bucket, self._value_column: agg}
            )
        return result
