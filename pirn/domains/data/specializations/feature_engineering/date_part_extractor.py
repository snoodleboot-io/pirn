"""``DatePartExtractor`` — decompose a datetime column into calendar parts.

The knot reads a single datetime column and appends individual columns
for each requested calendar part.  Each output column is named
``{source_column}_{part}`` (e.g. ``created_at_year``).

Supported parts: ``year``, ``month``, ``day``, ``hour``, ``weekday``,
``quarter``.

Algorithm:
    1. Receive resolved ``rows``, ``column``, and ``parts`` in
       ``process()``.
    2. Validate ``column`` identifier, non-empty ``parts``, and that all
       parts are in the supported set.
    3. For each row parse the datetime value (accepts ``datetime`` objects
       or ISO-8601 strings).
    4. Extract each requested part and append ``{column}_{part}`` columns.
    5. Return the enriched row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class DatePartExtractor(Knot):
    """Append calendar-part columns extracted from a datetime column."""

    _valid_parts: ClassVar[frozenset[str]] = frozenset(("year", "month", "day", "hour", "weekday", "quarter"))

    def __init__(
        self,
        *,
        rows: Knot | list,
        column: Knot | str,
        parts: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            column=column,
            parts=parts,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _extract(dt: datetime, part: str) -> int:
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
        self,
        *,
        rows: Any,
        column: Any,
        parts: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        IdentifierValidator.validate_column("column", column)
        parts_tuple = tuple(parts)
        if not parts_tuple:
            raise ValueError("DatePartExtractor: parts must be a non-empty sequence")
        invalid = set(parts_tuple) - self._valid_parts
        if invalid:
            raise ValueError(
                f"DatePartExtractor: unsupported parts {sorted(invalid)!r}; "
                f"allowed: {sorted(self._valid_parts)!r}"
            )

        def _as_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            dt = _as_dt(row[column])
            for part in parts_tuple:
                new_row[f"{column}_{part}"] = self._extract(dt, part)
            result.append(new_row)
        return result
