"""``WindowedDeduplicator`` — deduplicate within a sliding time window.

Events sharing the same key columns within ``window_minutes`` of each
other are considered duplicates; only the first arrival is kept.  An
event with the same key that arrives after the window has elapsed is
treated as a new, independent event.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class WindowedDeduplicator(Knot):
    """Keep the first event per key within a rolling time window."""

    def __init__(
        self,
        *,
        rows: Knot,
        key_columns: Sequence[str],
        timestamp_column: str,
        window_minutes: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(window_minutes, (int, float)) or window_minutes <= 0:
            raise ValueError(
                "WindowedDeduplicator: window_minutes must be a positive number"
            )
        self._key_columns = key_tuple
        self._timestamp_column = timestamp_column
        self._window = timedelta(minutes=window_minutes)
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Remove duplicate events that fall within the time window of their key predecessor.

        Rows must each carry a ``timestamp_column`` value that is either a
        :class:`datetime` or an ISO-8601 string.  Rows are processed in
        ascending timestamp order; the first occurrence of each key opens a
        window and any subsequent event for the same key within that window is
        dropped.  An event arriving after the window closes starts a new window.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Deduplicated rows in ascending timestamp order.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(rows, key=lambda r: _as_dt(r[self._timestamp_column]))
        last_seen: dict[tuple[Any, ...], datetime] = {}
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            key = tuple(row.get(c) for c in self._key_columns)
            ts = _as_dt(row[self._timestamp_column])
            prev = last_seen.get(key)
            if prev is None or (ts - prev) >= self._window:
                result.append(row)
                last_seen[key] = ts
        return result
