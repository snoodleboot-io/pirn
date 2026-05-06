"""``DataBatchToDuckdb`` — bridge knot from Tier-1 :class:`DataBatch` to
Tier-2 :class:`DuckdbDataBatch`.

Constructs a fresh in-memory connection (unless one is supplied),
materialises the rows into an in-process columnar table, and returns
the resulting deferred relation wrapped in a :class:`DuckdbDataBatch`.
``source_uri`` and ``fetched_at`` are propagated unchanged.

Used at the seam where a small upstream batch (fixture, glue) feeds
into a Tier-2 transform chain that expects a relational engine.

Algorithm:
    1. If ``connection`` is not None, validate it is a
       ``duckdb.DuckDBPyConnection``; otherwise open a fresh
       ``":memory:"`` connection.
    2. If ``batch.rows`` is empty, return a zero-row DuckDB relation
       (``SELECT NULL AS _empty WHERE FALSE``).
    3. Convert the rows to a ``polars.DataFrame`` to infer a coherent
       schema (nullable columns for absent keys).
    4. Export the DataFrame as an Arrow table and register it on the
       connection under a unique view name derived from the object
       identity of the Arrow table.
    5. Return a :class:`DuckdbDataBatch` wrapping the relation, with
       ``source_uri`` and ``fetched_at`` copied from the input batch.

    ```text
    conn = connection or duckdb.connect(":memory:")
    if not batch.rows:
        return DuckdbDataBatch(relation=conn.sql("SELECT NULL AS _empty WHERE FALSE"), ...)
    frame = pl.DataFrame(list(batch.rows))
    arrow = frame.to_arrow()
    view  = f"_pirn_rows_{id(arrow):x}"
    conn.register(view, arrow)
    return DuckdbDataBatch(relation=conn.table(view), ...)
    ```

References:
    [1] DuckDB Python API — in-process connection and relation API:
        https://duckdb.org/docs/api/python/overview
    [2] Polars — DataFrame.to_arrow (Arrow export):
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.to_arrow.html
    [3] DuckDB — registering Arrow tables as views:
        https://duckdb.org/docs/guides/python/sql_on_arrow
"""

from __future__ import annotations

from typing import Any

import duckdb
import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.duckdb.duckdb_connection import DuckDBConnection
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
        connection: Knot | DuckDBConnection | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, connection=connection, _config=_config, **kwargs)

    async def process(
        self, batch: DataBatch, connection: DuckDBConnection | None = None, **_: Any
    ) -> DuckdbDataBatch:
        """Load the Tier-1 DataBatch rows into a DuckDB relation and return a DuckdbDataBatch.

        Args:
            batch: The Tier-1 DataBatch whose rows are loaded into DuckDB.
            connection: An optional pre-existing :class:`DuckDBConnection`, or None to open a fresh one.

        Returns:
            A DuckdbDataBatch wrapping a DuckDB relation with the batch's rows.
        """
        if connection is not None and not isinstance(connection, DuckDBConnection):
            raise TypeError(
                "DataBatchToDuckdb: connection must be a DuckDBConnection or None"
            )
        raw_conn: duckdb.DuckDBPyConnection = (
            connection.conn if connection is not None else duckdb.connect(database=":memory:")
        )
        relation = self._build_relation(raw_conn, batch)
        return DuckdbDataBatch(
            relation=relation,
            connection=raw_conn,
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
