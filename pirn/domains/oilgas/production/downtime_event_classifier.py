"""``DowntimeEventClassifier`` — classify well downtime events from production data gaps."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DowntimeEventClassifier(Knot):
    """Classify downtime events detected as gaps in a production rate time series."""

    def __init__(
        self,
        *,
        production_series: Knot,
        gap_threshold_hours: float,
        categories: tuple[str, ...] = (
            "planned_maintenance",
            "unplanned_shutdown",
            "weather",
            "regulatory",
        ),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(gap_threshold_hours, (int, float)):
            raise TypeError(
                "DowntimeEventClassifier: gap_threshold_hours must be numeric"
            )
        if gap_threshold_hours <= 0:
            raise ValueError(
                "DowntimeEventClassifier: gap_threshold_hours must be positive"
            )
        self._gap_threshold_hours = float(gap_threshold_hours)
        self._categories = categories
        super().__init__(
            production_series=production_series, _config=_config, **kwargs
        )

    async def process(
        self, production_series: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Detect gaps in the production series and classify each as a downtime event.

        Args:
            production_series: List of dicts with ``timestamp_iso`` and
                ``rate_bopd`` entries in chronological order.

        Returns:
            List of downtime event dicts with ``start_iso``, ``end_iso``,
            ``duration_hours``, and ``category``.
        """
        default_category = self._categories[0] if self._categories else "unknown"
        events: list[dict[str, Any]] = []
        zero_start: str | None = None
        prev_ts: str | None = None
        for entry in production_series:
            ts: str = entry["timestamp_iso"]
            rate: float = float(entry.get("rate_bopd", 0.0))
            if rate == 0.0 and zero_start is None:
                zero_start = ts
            elif rate > 0.0 and zero_start is not None:
                events.append(
                    {
                        "start_iso": zero_start,
                        "end_iso": prev_ts or ts,
                        "duration_hours": self._gap_threshold_hours,
                        "category": default_category,
                    }
                )
                zero_start = None
            prev_ts = ts
        if zero_start is not None and prev_ts is not None:
            events.append(
                {
                    "start_iso": zero_start,
                    "end_iso": prev_ts,
                    "duration_hours": self._gap_threshold_hours,
                    "category": default_category,
                }
            )
        return events
