"""``ExactDeduplicator`` — remove exact duplicates on key columns.

When multiple rows share identical values for every key column, only one
survives. A tiebreaker column + sort direction determines which row is
kept from the tied group.
"""

from __future__ import annotations

from typing import Any, Literal, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ExactDeduplicator(Knot):
    """Keep one row per unique key, choosing the survivor by a tiebreaker column."""

    def __init__(
        self,
        *,
        rows: Knot,
        key_columns: Sequence[str],
        tiebreaker_column: str,
        tiebreaker_direction: Literal["asc", "desc"] = "desc",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_column("tiebreaker_column", tiebreaker_column)
        if tiebreaker_direction not in ("asc", "desc"):
            raise ValueError(
                "ExactDeduplicator: tiebreaker_direction must be 'asc' or 'desc'"
            )
        self._key_columns = key_tuple
        self._tiebreaker_column = tiebreaker_column
        self._tiebreaker_direction = tiebreaker_direction
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Deduplicate rows by keeping one survivor per unique key combination.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Deduplicated list of dicts; one row per unique key combination.
            Insertion order of first survivors is preserved when no tiebreaker
            distinguishes rows.
        """
        reverse = self._tiebreaker_direction == "desc"
        sorted_rows = sorted(
            rows,
            key=lambda r: r.get(self._tiebreaker_column),
            reverse=reverse,
        )
        seen: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in sorted_rows:
            key = tuple(row.get(c) for c in self._key_columns)
            if key not in seen:
                seen[key] = row
        return list(seen.values())
