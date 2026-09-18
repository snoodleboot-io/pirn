"""``DuckdbToDataBatch`` — bridge knot from Tier-2 :class:`DuckdbDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises the relation by calling ``relation.fetchall()`` and zipping
each row tuple with the relation's column names to produce row dicts —
only do this at the boundary where downstream knots actually need the
dict-based contract (a Tier-1 sink, a small validator, or a debug step).
For larger relations, prefer routing the :class:`DuckdbDataBatch`
directly into a Tier-2 sink.

Algorithm:
    1. Read the relation's column names via ``relation.columns``.
    2. Fetch every row as a positional tuple via ``relation.fetchall()``.
    3. Zip each row tuple with the column names to build one dict per row.
    4. Return a :class:`DataBatch` wrapping the row dicts, with
       ``source_uri`` and ``fetched_at`` copied from the input batch.

    ```text
    columns = relation.columns
    rows    = [dict(zip(columns, row)) for row in relation.fetchall()]
    return DataBatch(rows=rows, source_uri=batch.source_uri, fetched_at=batch.fetched_at)
    ```

References:
    [1] DuckDB Python API — DuckDBPyRelation.fetchall / .columns:
        https://duckdb.org/docs/api/python/reference/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.required_engine import RequiredEngine

from pirn_data.data_batch import DataBatch
from pirn_data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DuckdbToDataBatch(Knot):
    """Materialise a :class:`DuckdbDataBatch` back into a Tier-1 :class:`DataBatch`."""

    _required_engines: ClassVar[Sequence[RequiredEngine]] = (
        RequiredEngine("duckdb", extra="duckdb", package="pirn-data"),
    )

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DataBatch:
        """Fetch all rows from the DuckDB relation and return a Tier-1 DataBatch of row dicts.

        Args:
            batch: The DuckdbDataBatch whose relation is fetched to row dicts.

        Returns:
            A Tier-1 DataBatch containing the fetched rows with source_uri and fetched_at preserved.
        """
        columns = tuple(batch.relation.columns)
        fetched = batch.relation.fetchall()
        rows = tuple({columns[i]: value for i, value in enumerate(row)} for row in fetched)
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
