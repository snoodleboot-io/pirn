"""``DuckdbDeduplicate`` — Tier-2 dedup keeping the first occurrence per
key tuple.

DuckDB's relation API exposes ``.distinct()``, but that drops rows where
*every* column matches — we want first-occurrence-wins on a *subset* of
columns. Implemented here with a two-stage SQL plan:

1. Stamp every row with a stable ``ROW_NUMBER() OVER ()`` so we have a
   well-defined notion of "input order" within the relation.
2. Within each key partition, rank rows by that stamp and keep rank = 1.

This mirrors the Tier-1 :class:`Deduplicate` semantics. DuckDB executes
the window plan natively in C++.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class DuckdbDeduplicate(Knot):
    """Drop duplicate rows by key tuple, keeping the first occurrence."""

    def __init__(
        self,
        *,
        batch: Knot,
        keys: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_columns("DuckdbDeduplicate.keys", keys)
        self._keys: tuple[str, ...] = tuple(keys)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def keys(self) -> tuple[str, ...]:
        return self._keys

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DuckdbDataBatch:
        for column in batch.relation.columns:
            IdentifierValidator.validate_column(
                "DuckdbDeduplicate: upstream column", column
            )
        partition = ", ".join(f'"{key}"' for key in self._keys)
        original_columns = ", ".join(f'"{column}"' for column in batch.relation.columns)
        # Two-stage plan:
        #   stamped: every row gets a stable input-order index
        #   ranked:  ranked within each key partition by that index
        sql = (
            f"WITH stamped AS ("
            f"SELECT *, ROW_NUMBER() OVER () AS _pirn_input_idx FROM upstream"
            f"), ranked AS ("
            f"SELECT *, ROW_NUMBER() OVER ("
            f"PARTITION BY {partition} ORDER BY _pirn_input_idx"
            f") AS _pirn_rn FROM stamped"
            f") "
            f"SELECT {original_columns} FROM ranked WHERE _pirn_rn = 1 "
            f"ORDER BY _pirn_input_idx"
        )
        # Bind the upstream relation under the alias ``upstream`` so the
        # SQL can reference it. ``DuckDBPyRelation.query(alias, sql)``
        # scopes the alias to the call without leaking a global table.
        deduped = batch.relation.query("upstream", sql)
        return batch.with_relation(deduped)
