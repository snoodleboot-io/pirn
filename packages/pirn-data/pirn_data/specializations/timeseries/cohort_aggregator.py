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

Algorithm:
    1. Receive resolved ``rows``, ``user_column``, ``timestamp_column``,
       ``metric_column``, ``period_days``, and ``aggregation`` in
       ``process()``.
    2. Validate column identifiers, positive period_days, and aggregation
       membership in ``{"mean", "sum", "count"}``.
    3. Compute ``first_seen`` — the earliest timestamp per user.
    4. For each row compute ``period_idx = floor(days_since / period_days)``
       and accumulate users and metric values per ``(cohort_dt, period_idx)``.
    5. Collapse buckets using the chosen aggregation.
    6. Return rows sorted ascending by cohort then period.

Math:
    $period\\_idx = \\lfloor (t - t_{first}) / period\\_days \\rfloor$

    Mean: $\\bar{v} = \\frac{1}{N} \\sum_{i=1}^{N} v_i$

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class CohortAggregator(Knot):
    """Group users into cohorts and compute per-period retention metrics."""

    def __init__(
        self,
        *,
        rows: Knot | list[dict[str, Any]],
        user_column: Knot | str,
        timestamp_column: Knot | str,
        metric_column: Knot | str,
        period_days: Knot | int = 7,
        aggregation: Knot | str = "count",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            user_column=user_column,
            timestamp_column=timestamp_column,
            metric_column=metric_column,
            period_days=period_days,
            aggregation=aggregation,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _as_dt(val: Any) -> datetime:
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val))

    async def process(
        self,
        *,
        rows: Any,
        user_column: Any,
        timestamp_column: Any,
        metric_column: Any,
        period_days: Any = 7,
        aggregation: Any = "count",
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compute cohort retention metrics from event rows.

        Args:
            rows: Upstream event rows with user, timestamp, and metric columns.
            user_column: Column name identifying the user.
            timestamp_column: Column name for the event timestamp.
            metric_column: Column name for the metric to aggregate.
            period_days: Width of each cohort period in days.
            aggregation: One of ``"mean"``, ``"sum"``, ``"count"``.

        Returns:
            Rows aggregated by cohort and period, sorted by cohort then period.
        """
        IdentifierValidator.validate_column("user_column", user_column)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("metric_column", metric_column)
        if not isinstance(period_days, int) or period_days < 1:
            raise ValueError("CohortAggregator: period_days must be a positive integer")
        if aggregation not in ("mean", "sum", "count"):
            raise ValueError("CohortAggregator: aggregation must be mean/sum/count")

        period = timedelta(days=period_days)

        first_seen: dict[Any, datetime] = {}
        for row in rows:
            user = row.get(user_column)
            ts = self._as_dt(row[timestamp_column])
            if user not in first_seen or ts < first_seen[user]:
                first_seen[user] = ts

        bucket_users: dict[tuple[datetime, int], set[Any]] = {}
        bucket_values: dict[tuple[datetime, int], list[Any]] = {}
        for row in rows:
            user = row.get(user_column)
            ts = self._as_dt(row[timestamp_column])
            cohort_dt = first_seen[user]
            days_since = (ts - cohort_dt).days
            period_idx = int(days_since / period.days)
            key = (cohort_dt, period_idx)
            bucket_users.setdefault(key, set()).add(user)
            values = bucket_values.setdefault(key, [])
            metric = row.get(metric_column)
            if metric is not None:
                values.append(metric)

        result: list[dict[str, Any]] = []
        for (cohort_dt, period_idx), users in sorted(bucket_users.items()):
            vals = bucket_values[(cohort_dt, period_idx)]
            if not vals:
                metric_value = None
            elif aggregation == "count":
                metric_value = len(vals)
            elif aggregation == "sum":
                metric_value = sum(vals)
            else:
                metric_value = sum(vals) / len(vals)
            result.append(
                {
                    "cohort": cohort_dt.date().isoformat(),
                    "period": period_idx,
                    "users": len(users),
                    "metric_value": metric_value,
                }
            )
        return result
