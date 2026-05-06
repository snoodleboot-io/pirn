"""``RollingWindowAggregator`` — compute rolling window statistics.

For each row (ordered by ``timestamp_column``), the knot looks back
``window_size`` rows (inclusive) and computes the requested statistic
over ``value_column``.  The result is appended as a new column named
``{value_column}_{statistic}``.

Algorithm:
    1. Receive resolved ``rows``, ``timestamp_column``, ``value_column``,
       ``window_size``, and ``statistic`` in ``process()``.
    2. Validate column identifiers, positive window_size, and statistic
       membership in ``{"mean", "sum", "std", "min", "max"}``.
    3. Sort rows ascending by ``timestamp_column``.
    4. Slide a deque of ``maxlen=window_size`` over values, compute the
       statistic for each prefix/full window.
    5. Append ``{value_column}_{statistic}`` to each output row.

Math:
    Mean: $\\bar{v}_t = \\frac{1}{w} \\sum_{i=t-w+1}^{t} v_i$

    Std (population): $\\sigma_t = \\sqrt{\\frac{1}{w} \\sum_{i=t-w+1}^{t} (v_i - \\bar{v}_t)^2}$

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class RollingWindowAggregator(Knot):
    """Append a rolling statistic column to time-ordered rows."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        timestamp_column: Knot | str,
        value_column: Knot | str,
        window_size: Knot | int,
        statistic: Knot | str = "mean",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            timestamp_column=timestamp_column,
            value_column=value_column,
            window_size=window_size,
            statistic=statistic,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _apply(window: deque, statistic: str) -> float:
        vals = list(window)
        if statistic == "sum":
            return sum(vals)
        if statistic == "mean":
            return sum(vals) / len(vals)
        if statistic == "min":
            return min(vals)
        if statistic == "max":
            return max(vals)
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        return math.sqrt(variance)

    async def process(
        self,
        *,
        rows: Any,
        timestamp_column: Any,
        value_column: Any,
        window_size: Any,
        statistic: Any = "mean",
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Sort rows by timestamp and append the rolling statistic column.

        Args:
            rows: Upstream rows with ``timestamp_column`` and ``value_column``.
            timestamp_column: Column name for sorting and identification.
            value_column: Column name for the numeric values to aggregate.
            window_size: Number of rows to include in each rolling window.
            statistic: One of ``"mean"``, ``"sum"``, ``"std"``, ``"min"``, ``"max"``.

        Returns:
            Rows in ascending timestamp order with the new rolling statistic
            column (``{value_column}_{statistic}``) appended.
        """
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        IdentifierValidator.validate_column("value_column", value_column)
        if not isinstance(window_size, int) or window_size < 1:
            raise ValueError("RollingWindowAggregator: window_size must be a positive integer")
        if statistic not in ("mean", "sum", "std", "min", "max"):
            raise ValueError("RollingWindowAggregator: statistic must be mean/sum/std/min/max")

        output_column = f"{value_column}_{statistic}"

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(rows, key=lambda r: _as_dt(r[timestamp_column]))
        window: deque = deque(maxlen=window_size)
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            window.append(row[value_column])
            new_row = dict(row)
            new_row[output_column] = RollingWindowAggregator._apply(window, statistic)
            result.append(new_row)
        return result
