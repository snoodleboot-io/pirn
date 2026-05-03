"""``SessionizationKnot`` — group events into user sessions.

Events for the same entity are sorted by timestamp.  A new session
begins whenever the gap between consecutive events exceeds
``inactivity_minutes``.  Each event receives a ``session_id``
(``{entity_key}_{session_counter}``) and a ``session_seq`` (1-based
position within the session).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class SessionizationKnot(Knot):
    """Assign session_id and session_seq to each event row."""

    def __init__(
        self,
        *,
        rows: Knot,
        entity_columns: Sequence[str],
        timestamp_column: str,
        inactivity_minutes: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        entity_tuple = tuple(entity_columns)
        IdentifierValidator.validate_columns("entity_columns", entity_tuple)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(inactivity_minutes, (int, float)) or inactivity_minutes <= 0:
            raise ValueError(
                "SessionizationKnot: inactivity_minutes must be a positive number"
            )
        self._entity_columns = entity_tuple
        self._timestamp_column = timestamp_column
        self._gap = timedelta(minutes=inactivity_minutes)
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Group events into sessions and annotate each with session_id and session_seq.

        Events are processed in ascending timestamp order per entity.  A new
        session opens when the gap since the previous event exceeds
        ``inactivity_minutes``.

        Args:
            rows: Upstream event rows.

        Returns:
            Rows with ``session_id`` and ``session_seq`` columns added,
            in ascending timestamp order.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(
            rows, key=lambda r: _as_dt(r[self._timestamp_column])
        )
        last_ts: dict[tuple[Any, ...], datetime] = {}
        session_counter: dict[tuple[Any, ...], int] = {}
        session_seq: dict[tuple[Any, ...], int] = {}
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            entity = tuple(row.get(c) for c in self._entity_columns)
            ts = _as_dt(row[self._timestamp_column])
            prev = last_ts.get(entity)
            if prev is None or (ts - prev) > self._gap:
                session_counter[entity] = session_counter.get(entity, 0) + 1
                session_seq[entity] = 1
            else:
                session_seq[entity] = session_seq.get(entity, 0) + 1
            last_ts[entity] = ts
            entity_str = "_".join(str(v) for v in entity)
            sid = f"{entity_str}_{session_counter[entity]}"
            new_row = dict(row)
            new_row["session_id"] = sid
            new_row["session_seq"] = session_seq[entity]
            result.append(new_row)
        return result
