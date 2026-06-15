"""``LookupEnricher`` — left-join each row against an in-memory lookup table.

The lookup table is supplied as a list of dicts at construction time.
Each incoming row is matched by ``join_keys`` and the columns listed in
``enrich_columns`` are copied from the first matching lookup row.  If no
match is found the enrichment columns are set to ``None``.

Algorithm:
    1. Receive resolved ``rows``, ``lookup_table``, ``join_keys``, and
       ``enrich_columns`` in ``process()``.
    2. Validate ``join_keys`` and ``enrich_columns`` identifiers; validate
       that ``lookup_table`` is a list.
    3. Build an in-memory index from ``join_keys`` tuples to lookup rows.
    4. For each input row look up by join key; copy ``enrich_columns``
       from the matched lookup row or set them to ``None`` on miss.
    5. Return the enriched row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class LookupEnricher(Knot):
    """Enrich rows by left-joining against a static lookup table."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        lookup_table: Knot | list,
        join_keys: Knot | tuple[str, ...],
        enrich_columns: Knot | tuple[str, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            lookup_table=lookup_table,
            join_keys=join_keys,
            enrich_columns=enrich_columns,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        rows: Any,
        lookup_table: Any,
        join_keys: Any,
        enrich_columns: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        key_tuple = tuple(join_keys)
        enrich_tuple = tuple(enrich_columns)
        IdentifierValidator.validate_columns("join_keys", key_tuple)
        IdentifierValidator.validate_columns("enrich_columns", enrich_tuple)
        if not isinstance(lookup_table, list):
            raise TypeError("LookupEnricher: lookup_table must be a list of dicts")
        index: dict[tuple[Any, ...], dict[str, Any]] = {}
        for entry in lookup_table:
            key = tuple(entry.get(k) for k in key_tuple)
            if key not in index:
                index[key] = entry
        result: list[dict[str, Any]] = []
        for row in rows:
            key = tuple(row.get(k) for k in key_tuple)
            match = index.get(key)
            new_row = dict(row)
            for col in enrich_tuple:
                new_row[col] = match.get(col) if match else None
            result.append(new_row)
        return result
