"""``DatePartExtractor`` — decompose a datetime column into calendar parts.

The knot reads a single datetime column and appends individual columns
for each requested calendar part.  Each output column is named
``{source_column}_{part}`` (e.g. ``created_at_year``).

Supported parts: ``year``, ``month``, ``day``, ``hour``, ``weekday``,
``quarter``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator

_VALID_PARTS = frozenset(("year", "month", "day", "hour", "weekday", "quarter"))


class DatePartExtractor(Knot):
    """Append calendar-part columns extracted from a datetime column."""

    def __init__(
        self,
        *,
        rows: Knot,
        column: str,
        parts: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("column", column)
        parts_tuple = tuple(parts)
        if not parts_tuple:
            raise ValueError(
                "DatePartExtractor: parts must be a non-empty sequence"
            )
        invalid = set(parts_tuple) - _VALID_PARTS
        if invalid:
            raise ValueError(
                f"DatePartExtractor: unsupported parts {sorted(invalid)!r}; "
                f"allowed: {sorted(_VALID_PARTS)!r}"
            )
        self._column = column
        self._parts = parts_tuple
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _extract(self, dt: datetime, part: str) -> int:
        if part == "year":
            return dt.year
        if part == "month":
            return dt.month
        if part == "day":
            return dt.day
        if part == "hour":
            return dt.hour
        if part == "weekday":
            return dt.weekday()
        return (dt.month - 1) // 3 + 1

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Extract requested calendar parts from the datetime column.

        Args:
            rows: Upstream rows with a datetime or ISO-8601 string in
                  ``column``.

        Returns:
            Rows with new ``{column}_{part}`` columns appended.
        """
        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            dt = _as_dt(row[self._column])
            for part in self._parts:
                new_row[f"{self._column}_{part}"] = self._extract(dt, part)
            result.append(new_row)
        return result
