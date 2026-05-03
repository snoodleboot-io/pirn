"""``CohortAggregator`` — retention and metric aggregates by cohort.

Users are assigned to cohorts based on the date of their first event
(the cohort date).  For each subsequent period (in units of
``period_days``), the aggregation function is applied to the metric
column for all users in that cohort.

Result schema:
  * ``cohort``        — cohort date (date of first event, as ISO-8601 string)
  * ``period``        — period index (0 = cohort acquisition period)
  * ``users``         — distinct users active in this cohort+period
  * ``metric_value``  — aggregated metric (or None when no data)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class CohortAggregator(Knot):
    """Group users into cohorts and compute per-period retention metrics."""

    def __init__(
        self,
        *,
        rows: Knot,
        user_column: str,
        timestamp_column: str,
        metric_column: str,
        period_days: int = 7,
        aggregation: Literal["mean", "sum", "count"] = "count",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("user_column", user_column)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("metric_column", metric_column)
        if not isinstance(period_days, int) or period_days < 1:
            raise ValueError(
                "CohortAggregator: period_days must be a positive integer"
            )
        if aggregation not in ("mean", "sum", "count"):
            raise ValueError(
                "CohortAggregator: aggregation must be mean/sum/count"
            )
        self._user_column = user_column
        self._timestamp_column = timestamp_column
        self._metric_column = metric_column
        self._period = timedelta(days=period_days)
        self._aggregation = aggregation
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Compute cohort retention metrics from event rows.

        Args:
            rows: Upstream event rows with user, timestamp, and metric columns.

        Returns:
            Rows aggregated by cohort and period, sorted by cohort then period.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        first_seen: dict[Any, datetime] = {}
        for row in rows:
            user = row.get(self._user_column)
            ts = _as_dt(row[self._timestamp_column])
            if user not in first_seen or ts < first_seen[user]:
                first_seen[user] = ts

        bucket: dict[tuple[datetime, int], dict] = {}
        for row in rows:
            user = row.get(self._user_column)
            ts = _as_dt(row[self._timestamp_column])
            cohort_dt = first_seen[user]
            days_since = (ts - cohort_dt).days
            period_idx = int(days_since / self._period.days)
            key = (cohort_dt, period_idx)
            if key not in bucket:
                bucket[key] = {"users": set(), "values": []}
            bucket[key]["users"].add(user)
            metric = row.get(self._metric_column)
            if metric is not None:
                bucket[key]["values"].append(metric)

        result: list[dict[str, Any]] = []
        for (cohort_dt, period_idx), data in sorted(bucket.items()):
            vals = data["values"]
            if not vals:
                metric_value = None
            elif self._aggregation == "count":
                metric_value = len(vals)
            elif self._aggregation == "sum":
                metric_value = sum(vals)
            else:
                metric_value = sum(vals) / len(vals)
            result.append(
                {
                    "cohort": cohort_dt.date().isoformat(),
                    "period": period_idx,
                    "users": len(data["users"]),
                    "metric_value": metric_value,
                }
            )
        return result
