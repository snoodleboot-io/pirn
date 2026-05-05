"""``TimeSeriesResampler`` — resample time-series to a target frequency.

Rows are grouped into fixed-width time buckets of ``frequency_seconds``
and each group is collapsed using the configured aggregation function
(mean / sum / last / first).  The bucket timestamp is the floor of the
original timestamp.

Algorithm:
    1. Receive resolved ``rows``, ``timestamp_column``, ``value_column``,
       ``frequency_seconds``, and ``aggregation`` in ``process()``.
    2. Validate column identifiers, positive frequency_seconds, and
       aggregation membership in ``{"mean", "sum", "last", "first"}``.
    3. Assign each row to a bucket via the floor of its timestamp.
    4. Collapse each bucket using the chosen aggregation.
    5. Return buckets sorted ascending by bucket timestamp.

Math:
    $bucket = \\lfloor t / frequency\\_seconds \\rfloor \\times frequency\\_seconds$

    Mean: $\\bar{v} = \\frac{1}{N} \\sum_{i=1}^{N} v_i$

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class TimeSeriesResampler(Knot):
    """Collapse time-series rows into fixed-frequency buckets."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        timestamp_column: Knot | str,
        value_column: Knot | str,
        frequency_seconds: Knot | float,
        aggregation: Knot | str = "mean",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            timestamp_column=timestamp_column,
            value_column=value_column,
            frequency_seconds=frequency_seconds,
            aggregation=aggregation,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _floor(dt: datetime, frequency: timedelta) -> datetime:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        if dt.tzinfo is None:
            epoch = datetime(1970, 1, 1)
        freq_s = frequency.total_seconds()
        since = (dt - epoch).total_seconds()
        return epoch + timedelta(seconds=(since // freq_s) * freq_s)

    async def process(
        self,
        *,
        rows: Any,
        timestamp_column: Any,
        value_column: Any,
        frequency_seconds: Any,
        aggregation: Any = "mean",
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Resample rows to the target frequency using the configured aggregation.

        Args:
            rows: Upstream rows; each must have ``timestamp_column`` (datetime or
                  ISO-8601 string) and ``value_column`` (numeric).
            timestamp_column: Column name for timestamps.
            value_column: Column name for numeric values.
            frequency_seconds: Bucket width in seconds; must be positive.
            aggregation: One of ``"mean"``, ``"sum"``, ``"last"``, ``"first"``.

        Returns:
            One row per bucket with ``timestamp_column`` set to the bucket floor
            and ``value_column`` set to the aggregated value, sorted ascending.
        """
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

        frequency = timedelta(seconds=frequency_seconds)

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        buckets: dict[datetime, list[Any]] = {}
        bucket_order: list[datetime] = []
        for row in rows:
            ts = _as_dt(row[timestamp_column])
            bucket = TimeSeriesResampler._floor(ts, frequency)
            if bucket not in buckets:
                buckets[bucket] = []
                bucket_order.append(bucket)
            buckets[bucket].append(row[value_column])

        result: list[dict[str, Any]] = []
        for bucket in sorted(bucket_order):
            vals = buckets[bucket]
            if aggregation == "mean":
                agg = sum(vals) / len(vals)
            elif aggregation == "sum":
                agg = sum(vals)
            elif aggregation == "first":
                agg = vals[0]
            else:
                agg = vals[-1]
            result.append({timestamp_column: bucket, value_column: agg})
        return result
