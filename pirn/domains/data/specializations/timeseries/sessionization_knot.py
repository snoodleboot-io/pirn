"""``SessionizationKnot`` — group events into user sessions.

Events for the same entity are sorted by timestamp.  A new session
begins whenever the gap between consecutive events exceeds
``inactivity_minutes``.  Each event receives a ``session_id``
(``{entity_key}_{session_counter}``) and a ``session_seq`` (1-based
position within the session).

Algorithm:
    1. Receive resolved ``rows``, ``entity_columns``, ``timestamp_column``,
       and ``inactivity_minutes`` in ``process()``.
    2. Validate column identifiers and positive inactivity_minutes.
    3. Sort all rows ascending by ``timestamp_column``.
    4. For each row, derive the entity key tuple and compute the gap from
       the previous event of the same entity.
    5. Open a new session when the gap exceeds ``inactivity_minutes`` or
       when no prior event exists.
    6. Assign ``session_id = "{entity_str}_{counter}"`` and ``session_seq``.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class SessionizationKnot(Knot):
    """Assign session_id and session_seq to each event row."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        entity_columns: Knot | Sequence[str],
        timestamp_column: Knot | str,
        inactivity_minutes: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            entity_columns=entity_columns,
            timestamp_column=timestamp_column,
            inactivity_minutes=inactivity_minutes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        entity_columns: Any,
        timestamp_column: Any,
        inactivity_minutes: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Group events into sessions and annotate each with session_id and session_seq.

        Args:
            rows: Upstream event rows.
            entity_columns: Column names that together identify an entity.
            timestamp_column: Column name for event timestamps.
            inactivity_minutes: Minutes of inactivity that open a new session.

        Returns:
            Rows with ``session_id`` and ``session_seq`` columns added,
            in ascending timestamp order.
        """
        entity_tuple = tuple(entity_columns)
        IdentifierValidator.validate_columns("entity_columns", entity_tuple)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(inactivity_minutes, (int, float)) or inactivity_minutes <= 0:
            raise ValueError("SessionizationKnot: inactivity_minutes must be a positive number")

        gap = timedelta(minutes=inactivity_minutes)

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        sorted_rows = sorted(rows, key=lambda r: _as_dt(r[timestamp_column]))
        last_ts: dict[tuple[Any, ...], datetime] = {}
        session_counter: dict[tuple[Any, ...], int] = {}
        session_seq: dict[tuple[Any, ...], int] = {}
        result: list[dict[str, Any]] = []
        for row in sorted_rows:
            entity = tuple(row.get(c) for c in entity_tuple)
            ts = _as_dt(row[timestamp_column])
            prev = last_ts.get(entity)
            if prev is None or (ts - prev) > gap:
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
