"""``LookupEnricher`` — left-join each row against an in-memory lookup table.

The lookup table is supplied as a list of dicts at construction time.
Each incoming row is matched by ``join_keys`` and the columns listed in
``enrich_columns`` are copied from the first matching lookup row.  If no
match is found the enrichment columns are set to ``None``.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class LookupEnricher(Knot):
    """Enrich rows by left-joining against a static lookup table."""

    def __init__(
        self,
        *,
        rows: Knot,
        lookup_table: list[dict[str, Any]],
        join_keys: Sequence[str],
        enrich_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        key_tuple = tuple(join_keys)
        enrich_tuple = tuple(enrich_columns)
        IdentifierValidator.validate_columns("join_keys", key_tuple)
        IdentifierValidator.validate_columns("enrich_columns", enrich_tuple)
        if not isinstance(lookup_table, list):
            raise TypeError(
                "LookupEnricher: lookup_table must be a list of dicts"
            )
        self._join_keys = key_tuple
        self._enrich_columns = enrich_tuple
        self._index: dict[tuple[Any, ...], dict[str, Any]] = {}
        for entry in lookup_table:
            key = tuple(entry.get(k) for k in self._join_keys)
            if key not in self._index:
                self._index[key] = entry
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Left-join each row against the lookup table.

        Args:
            rows: Upstream rows to enrich.

        Returns:
            Rows with enrichment columns appended; unmatched rows receive
            ``None`` for each enrichment column.
        """
        result: list[dict[str, Any]] = []
        for row in rows:
            key = tuple(row.get(k) for k in self._join_keys)
            match = self._index.get(key)
            new_row = dict(row)
            for col in self._enrich_columns:
                new_row[col] = match.get(col) if match else None
            result.append(new_row)
        return result
