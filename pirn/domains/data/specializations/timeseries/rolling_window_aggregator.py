"""``RollingWindowAggregator`` — compute rolling window statistics.

For each row (ordered by ``timestamp_column``), the knot looks back
``window_size`` rows (inclusive) and computes the requested statistic
over ``value_column``.  The result is appended as a new column named
``{value_column}_{statistic}``.
"""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime
from typing import Any, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class RollingWindowAggregator(Knot):
    """Append a rolling statistic column to time-ordered rows."""

    def __init__(
        self,
        *,
        rows: Knot,
        timestamp_column: str,
        value_column: str,
        window_size: int,
        statistic: Literal["mean", "sum", "std", "min", "max"] = "mean",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("value_column", value_column)
        if not isinstance(window_size, int) or window_size < 1:
            raise ValueError(
                "RollingWindowAggregator: window_size must be a positive integer"
            )
        if statistic not in ("mean", "sum", "std", "min", "max"):
            raise ValueError(
                "RollingWindowAggregator: statistic must be mean/sum/std/min/max"
            )
        self._timestamp_column = timestamp_column
        self._value_column = value_column
        self._window_size = window_size
        self._statistic = statistic
        self._output_column = f"{value_column}_{statistic}"
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _apply(self, window: deque) -> float:
        vals = list(window)
        if self._statistic == "sum":
            return sum(vals)
        if self._statistic == "mean":
            return sum(vals) / len(vals)
        if self._statistic == "min":
            return min(vals)
        if self._statistic == "max":
            return max(vals)
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        return math.sqrt(variance)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Sort rows by timestamp and append the rolling statistic column.

        Args:
            rows: Upstream rows with ``timestamp_column`` and ``value_column``.

        Returns:
            Rows in ascending timestamp order with the new rolling statistic
            column (``{value_column}_{statistic}``) appended.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(
            rows, key=lambda r: _as_dt(r[self._timestamp_column])
        )
        window: deque = deque(maxlen=self._window_size)
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            window.append(row[self._value_column])
            new_row = dict(row)
            new_row[self._output_column] = self._apply(window)
            result.append(new_row)
        return result
