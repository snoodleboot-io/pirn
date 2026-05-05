"""``ExactDeduplicator`` — remove exact duplicates on key columns.

When multiple rows share identical values for every key column, only one
survives. A tiebreaker column + sort direction determines which row is
kept from the tied group.

Algorithm:
    1. Receive resolved ``rows``, ``key_columns``, ``tiebreaker_column``,
       and ``tiebreaker_direction`` in ``process()``.
    2. Validate all inputs: identifier safety and direction value.
    3. Sort rows by ``tiebreaker_column`` in the specified direction.
    4. Iterate through sorted rows; keep the first occurrence of each
       unique key combination (dict-keyed by the key tuple).
    5. Return the surviving rows preserving sorted order.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ExactDeduplicator(Knot):
    """Keep one row per unique key, choosing the survivor by a tiebreaker column."""

    def __init__(
        self,
        *,
        rows: Knot,
        key_columns: Knot | tuple[str, ...],
        tiebreaker_column: Knot | str,
        tiebreaker_direction: Knot | Literal["asc", "desc"],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            key_columns=key_columns,
            tiebreaker_column=tiebreaker_column,
            tiebreaker_direction=tiebreaker_direction,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        key_columns: Any,
        tiebreaker_column: Any,
        tiebreaker_direction: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        if not isinstance(tiebreaker_column, str) or not tiebreaker_column:
            raise ValueError(
                "ExactDeduplicator: tiebreaker_column must be a non-empty string"
            )
        IdentifierValidator.validate_column("tiebreaker_column", tiebreaker_column)
        if tiebreaker_direction not in ("asc", "desc"):
            raise ValueError(
                "ExactDeduplicator: tiebreaker_direction must be 'asc' or 'desc'"
            )
        reverse = tiebreaker_direction == "desc"
        sorted_rows = sorted(
            rows,
            key=lambda r: r.get(tiebreaker_column),
            reverse=reverse,
        )
        seen: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in sorted_rows:
            key = tuple(row.get(c) for c in key_tuple)
            if key not in seen:
                seen[key] = row
        return list(seen.values())
