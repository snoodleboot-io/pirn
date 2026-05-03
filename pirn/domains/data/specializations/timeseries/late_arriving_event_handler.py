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
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class LateArrivingEventHandler(Knot):
    """Forward events and emit bucket corrections for late arrivals."""

    def __init__(
        self,
        *,
        rows: Knot,
        timestamp_column: str,
        value_column: str,
        bucket_seconds: float,
        allowed_lateness_seconds: float,
        aggregation: Literal["mean", "sum", "count"] = "sum",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("value_column", value_column)
        for name, val in (
            ("bucket_seconds", bucket_seconds),
            ("allowed_lateness_seconds", allowed_lateness_seconds),
        ):
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(
                    f"LateArrivingEventHandler: {name} must be a positive number"
                )
        if aggregation not in ("mean", "sum", "count"):
            raise ValueError(
                "LateArrivingEventHandler: aggregation must be mean/sum/count"
            )
        self._timestamp_column = timestamp_column
        self._value_column = value_column
        self._bucket = timedelta(seconds=bucket_seconds)
        self._lateness = timedelta(seconds=allowed_lateness_seconds)
        self._aggregation = aggregation
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _floor(self, dt: datetime) -> datetime:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if dt.tzinfo is None:
            epoch = datetime(1970, 1, 1)
        freq_s = self._bucket.total_seconds()
        since = (dt - epoch).total_seconds()
        return epoch + timedelta(seconds=(since // freq_s) * freq_s)

    def _agg(self, vals: list[Any]) -> Any:
        if self._aggregation == "count":
            return len(vals)
        if self._aggregation == "sum":
            return sum(vals)
        return sum(vals) / len(vals)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Process events and emit corrections for any late arrivals.

        The watermark is set to the maximum timestamp seen so far. Events
        older than watermark - allowed_lateness are classified as late.
        For each late event the affected bucket aggregate is recomputed and
        emitted as a correction record.

        Args:
            rows: Upstream event rows.

        Returns:
            All forwarded rows (with ``is_correction=False``) plus any
            correction rows (with ``is_correction=True``).
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        # Process rows in arrival order so the watermark reflects what has
        # already been committed; late rows are those whose timestamp lags
        # behind the advancing watermark by more than allowed_lateness.
        buckets: dict[datetime, list[Any]] = {}
        result: list[dict[str, Any]] = []
        watermark: datetime | None = None
        corrections: dict[datetime, dict[str, Any]] = {}

        for row in rows:
            ts = _as_dt(row[self._timestamp_column])
            if watermark is None or ts > watermark:
                watermark = ts
            bucket = self._floor(ts)
            buckets.setdefault(bucket, []).append(row[self._value_column])
            is_late = watermark is not None and ts < (watermark - self._lateness)
            forwarded = dict(row)
            forwarded["is_correction"] = False
            result.append(forwarded)
            if is_late:
                correction = {
                    self._timestamp_column: bucket,
                    self._value_column: self._agg(buckets[bucket]),
                    "is_correction": True,
                    "correction_for_bucket": bucket,
                }
                corrections[bucket] = correction

        result.extend(corrections.values())
        return result
