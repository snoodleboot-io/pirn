"""``WindowedDeduplicator`` — deduplicate within a sliding time window.

Events sharing the same key columns within ``window_minutes`` of each
other are considered duplicates; only the first arrival is kept.  An
event with the same key that arrives after the window has elapsed is
treated as a new, independent event.

Algorithm:
    1. Receive resolved ``rows``, ``key_columns``, ``timestamp_column``,
       and ``window_minutes`` in ``process()``.
    2. Validate all inputs: identifier safety and positive window.
    3. Sort rows by ``timestamp_column`` ascending.
    4. Track the last-seen timestamp per key tuple.
    5. For each row, if no previous occurrence exists OR the elapsed time
       since the last occurrence is >= the window, emit the row and update
       the last-seen timestamp.
    6. Return the surviving rows in ascending timestamp order.

References:
    [1] pirn — IdentifierValidator:
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class WindowedDeduplicator(Knot):
    """Keep the first event per key within a rolling time window."""

    def __init__(
        self,
        *,
        rows: Knot,
        key_columns: Knot | tuple[str, ...],
        timestamp_column: Knot | str,
        window_minutes: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            key_columns=key_columns,
            timestamp_column=timestamp_column,
            window_minutes=window_minutes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        key_columns: Any,
        timestamp_column: Any,
        window_minutes: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        if not isinstance(timestamp_column, str) or not timestamp_column:
            raise ValueError("WindowedDeduplicator: timestamp_column must be a non-empty string")
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(window_minutes, (int, float)) or window_minutes <= 0:
            raise ValueError("WindowedDeduplicator: window_minutes must be a positive number")
        window = timedelta(minutes=window_minutes)

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(rows, key=lambda r: _as_dt(r[timestamp_column]))
        last_seen: dict[tuple[Any, ...], datetime] = {}
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            key = tuple(row.get(c) for c in key_tuple)
            ts = _as_dt(row[timestamp_column])
            prev = last_seen.get(key)
            if prev is None or (ts - prev) >= window:
                result.append(row)
                last_seen[key] = ts
        return result
