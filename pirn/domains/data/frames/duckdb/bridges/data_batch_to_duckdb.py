"""``DataBatchToDuckdb`` — bridge knot from Tier-1 :class:`DataBatch` to
Tier-2 :class:`DuckdbDataBatch`.

Constructs a fresh in-memory connection (unless one is supplied),
materialises the rows into an in-process columnar table, and returns
the resulting deferred relation wrapped in a :class:`DuckdbDataBatch`.
``source_uri`` and ``fetched_at`` are propagated unchanged.

Used at the seam where a small upstream batch (fixture, glue) feeds
into a Tier-2 transform chain that expects a relational engine.
"""

from __future__ import annotations

from typing import Any

import duckdb
import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DataBatchToDuckdb(Knot):
    """Construct a :class:`DuckdbDataBatch` from a Tier-1 :class:`DataBatch`.

    A caller may inject a pre-existing ``connection`` so several bridges
    share a single in-process DuckDB database. Otherwise a fresh
    ``:memory:`` connection is opened per knot invocation.
    """

    def __init__(
        self,
        *,
        batch: Knot,
        connection: duckdb.DuckDBPyConnection | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._connection = connection
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DataBatch, **_: Any) -> DuckdbDataBatch:
        connection = self._connection
        if connection is None:
            connection = duckdb.connect(database=":memory:")
        relation = self._build_relation(connection, batch)
        return DuckdbDataBatch(
            relation=relation,
            connection=connection,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )

    def _build_relation(
        self,
        connection: duckdb.DuckDBPyConnection,
        batch: DataBatch,
    ) -> duckdb.DuckDBPyRelation:
        if not batch.rows:
            # Empty: hand back a zero-row relation with no columns. DuckDB
            # does not have a literal "empty relation" constructor, but a
            # SELECT that always filters to zero rows is functionally
            # equivalent for downstream knots.
            return connection.sql("SELECT NULL AS _empty WHERE FALSE")
        # Polars infers a coherent schema from row dicts (union of keys,
        # nullable for missing). DuckDB ingests the resulting Arrow
        # table — registered under a unique view name so multiple
        # bridges on the same connection don't collide.
        frame = pl.DataFrame(list(batch.rows))
        arrow_table = frame.to_arrow()
        view_name = f"_pirn_rows_{id(arrow_table):x}"
        connection.register(view_name, arrow_table)
        return connection.table(view_name)
