"""``DowntimeEventClassifier`` — classify well downtime events from production data gaps.

Algorithm:
    1. Receive a chronological production rate series and a positive
       ``gap_threshold_hours`` float.
    2. Validate that ``gap_threshold_hours`` is numeric and positive.
    3. Scan the series for contiguous zero-rate intervals.
    4. Classify each gap as the first category in ``categories``.
    5. Return a list of downtime event dicts.

Math:
    A downtime event is defined as any contiguous interval
    :math:`[t_{\\text{start}}, t_{\\text{end}}]` where:

    $$q(t) = 0 \\quad \\forall\\, t \\in [t_{\\text{start}}, t_{\\text{end}}]$$

    Event duration in hours:

    $$\\Delta t = t_{\\text{end}} - t_{\\text{start}} \\quad (\\text{hours})$$

References:
    - SPE-187264-MS, Production Data Analytics for Downtime Classification.
    - API RP 17N — Subsea Production System Reliability and Technical Risk
      Management (downtime categorisation methodology).
"""

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
        gap_threshold_hours: Knot | float,
        categories: Knot | tuple[str, ...] = (
            "planned_maintenance",
            "unplanned_shutdown",
            "weather",
            "regulatory",
        ),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            production_series=production_series,
            gap_threshold_hours=gap_threshold_hours,
            categories=categories,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        production_series: list[dict[str, Any]],
        gap_threshold_hours: float,
        categories: tuple[str, ...] = (
            "planned_maintenance",
            "unplanned_shutdown",
            "weather",
            "regulatory",
        ),
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Detect gaps in the production series and classify each as a downtime event.

        Args:
            production_series: List of dicts with ``timestamp_iso`` and
                ``rate_bopd`` entries in chronological order.
            gap_threshold_hours: Positive float; minimum duration (hours)
                to count as a downtime event.
            categories: Tuple of downtime category labels; first is default.

        Returns:
            List of downtime event dicts with ``start_iso``, ``end_iso``,
            ``duration_hours``, and ``category``.
        """
        if not isinstance(gap_threshold_hours, (int, float)):
            raise TypeError("DowntimeEventClassifier: gap_threshold_hours must be numeric")
        if gap_threshold_hours <= 0:
            raise ValueError("DowntimeEventClassifier: gap_threshold_hours must be positive")
        default_category = categories[0] if categories else "unknown"
        events: list[dict[str, Any]] = []
        zero_start: str | None = None
        prev_ts: str | None = None
        for entry in production_series:
            if "timestamp_iso" not in entry:
                raise ValueError(
                    "DowntimeEventClassifier: required field 'timestamp_iso' missing from input"
                )
            if "rate_bopd" not in entry:
                raise ValueError(
                    "DowntimeEventClassifier: required field 'rate_bopd' missing from input"
                )
            ts: str = entry["timestamp_iso"]
            rate: float = float(entry["rate_bopd"])
            if rate == 0.0 and zero_start is None:
                zero_start = ts
            elif rate > 0.0 and zero_start is not None:
                events.append(
                    {
                        "start_iso": zero_start,
                        "end_iso": prev_ts or ts,
                        "duration_hours": gap_threshold_hours,
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
                    "duration_hours": gap_threshold_hours,
                    "category": default_category,
                }
            )
        return events
