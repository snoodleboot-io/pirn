"""``LateArrivingEventHandler`` — accept late events and emit correction records.

When a late event arrives (its timestamp is older than the current
watermark minus ``allowed_lateness_seconds``), the knot recomputes the
aggregate for the affected time bucket and emits a correction record
alongside the original.

A correction record is a copy of the aggregated bucket row with an
additional ``is_correction`` flag set to ``True`` and
``correction_for_bucket`` set to the bucket timestamp.

Rows that arrive within lateness are forwarded unchanged with
``is_correction=False``.

Algorithm:
    1. Receive resolved ``rows``, ``timestamp_column``, ``value_column``,
       ``bucket_seconds``, ``allowed_lateness_seconds``, and ``aggregation``
       in ``process()``.
    2. Validate column identifiers, positive numeric thresholds, and
       aggregation membership in ``{"mean", "sum", "count"}``.
    3. Advance the watermark to the maximum timestamp seen so far.
    4. For each row: compute the bucket floor; append to bucket accumulator;
       detect late rows (ts < watermark - lateness).
    5. For each late row, recompute and upsert a correction record.
    6. Return all forwarded rows plus correction records.

Math:
    $bucket = \\lfloor t / bucket\\_seconds \\rfloor \\times bucket\\_seconds$

    Late: $t < watermark - allowed\\_lateness\\_seconds$

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class LateArrivingEventHandler(Knot):
    """Forward events and emit bucket corrections for late arrivals."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        timestamp_column: Knot | str,
        value_column: Knot | str,
        bucket_seconds: Knot | float,
        allowed_lateness_seconds: Knot | float,
        aggregation: Knot | str = "sum",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            timestamp_column=timestamp_column,
            value_column=value_column,
            bucket_seconds=bucket_seconds,
            allowed_lateness_seconds=allowed_lateness_seconds,
            aggregation=aggregation,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _floor(dt: datetime, bucket: timedelta) -> datetime:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        if dt.tzinfo is None:
            epoch = datetime(1970, 1, 1)
        freq_s = bucket.total_seconds()
        since = (dt - epoch).total_seconds()
        return epoch + timedelta(seconds=(since // freq_s) * freq_s)

    @staticmethod
    def _agg(vals: list[Any], aggregation: str) -> Any:
        if aggregation == "count":
            return len(vals)
        if aggregation == "sum":
            return sum(vals)
        return sum(vals) / len(vals)

    async def process(
        self,
        *,
        rows: Any,
        timestamp_column: Any,
        value_column: Any,
        bucket_seconds: Any,
        allowed_lateness_seconds: Any,
        aggregation: Any = "sum",
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Process events and emit corrections for any late arrivals.

        Args:
            rows: Upstream event rows.
            timestamp_column: Column name for the event timestamp.
            value_column: Column name for the numeric value to aggregate.
            bucket_seconds: Width of each time bucket in seconds.
            allowed_lateness_seconds: Events older than watermark minus this
                are classified as late.
            aggregation: One of ``"mean"``, ``"sum"``, ``"count"``.

        Returns:
            All forwarded rows (with ``is_correction=False``) plus any
            correction rows (with ``is_correction=True``).
        """
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("value_column", value_column)
        for name, val in (
            ("bucket_seconds", bucket_seconds),
            ("allowed_lateness_seconds", allowed_lateness_seconds),
        ):
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(f"LateArrivingEventHandler: {name} must be a positive number")
        if aggregation not in ("mean", "sum", "count"):
            raise ValueError("LateArrivingEventHandler: aggregation must be mean/sum/count")

        bucket_td = timedelta(seconds=bucket_seconds)
        lateness_td = timedelta(seconds=allowed_lateness_seconds)

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        buckets: dict[datetime, list[Any]] = {}
        result: list[dict[str, Any]] = []
        watermark: datetime | None = None
        corrections: dict[datetime, dict[str, Any]] = {}

        for row in rows:
            ts = _as_dt(row[timestamp_column])
            if watermark is None or ts > watermark:
                watermark = ts
            bucket = LateArrivingEventHandler._floor(ts, bucket_td)
            buckets.setdefault(bucket, []).append(row[value_column])
            is_late = watermark is not None and ts < (watermark - lateness_td)
            forwarded = dict(row)
            forwarded["is_correction"] = False
            result.append(forwarded)
            if is_late:
                correction = {
                    timestamp_column: bucket,
                    value_column: LateArrivingEventHandler._agg(buckets[bucket], aggregation),
                    "is_correction": True,
                    "correction_for_bucket": bucket,
                }
                corrections[bucket] = correction

        result.extend(corrections.values())
        return result
