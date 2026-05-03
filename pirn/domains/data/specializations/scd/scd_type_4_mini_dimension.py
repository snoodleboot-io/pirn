"""``ScdType4MiniDimension`` — Slowly Changing Dimension Type 4 (mini-dimension).

SCD Type 4 splits rapidly-changing attributes out of the main dimension
into a separate *mini-dimension* table. The main dimension retains a
stable, slowly-changing key while the mini-dimension is looked up via a
foreign key stored on the fact table.

Behaviour
---------
For each row from ``source_query``:

1. Look up the mini-dimension table by the ``mini_dim_attributes`` values.
2. If a matching mini-dim row exists → reuse its surrogate key.
3. If not → insert a new mini-dim row and return the new surrogate key.
4. Update the corresponding main-dim row's foreign-key column
   (``fact_fk_column``) to point at the current mini-dim surrogate key.

The mini-dimension table must have an auto-increment surrogate key column
named ``mini_dim_key_column`` (default ``mini_dim_sk``).
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ScdType4MiniDimension(SubTapestry):
    """Split rapidly-changing attributes into a mini-dimension table (SCD Type 4)."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        main_pool: DatabaseConnectionPool,
        main_table: str,
        main_key_columns: Sequence[str],
        fact_fk_column: str,
        mini_pool: DatabaseConnectionPool,
        mini_table: str,
        mini_dim_attributes: Sequence[str],
        mini_dim_key_column: str = "mini_dim_sk",
        source_key_columns: Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, pool in (
            ("source_pool", source_pool),
            ("main_pool", main_pool),
            ("mini_pool", mini_pool),
        ):
            if not isinstance(pool, DatabaseConnectionPool):
                raise TypeError(
                    f"ScdType4MiniDimension: {label} must be a DatabaseConnectionPool"
                )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError(
                "ScdType4MiniDimension: source_query must be a non-empty string"
            )
        for label, value in (
            ("main_table", main_table),
            ("mini_table", mini_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType4MiniDimension: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("main_table", main_table)
        IdentifierValidator.validate_column("mini_table", mini_table)
        IdentifierValidator.validate_column("fact_fk_column", fact_fk_column)
        IdentifierValidator.validate_column(
            "mini_dim_key_column", mini_dim_key_column
        )
        main_key_tuple = tuple(main_key_columns)
        IdentifierValidator.validate_columns("main_key_columns", main_key_tuple)
        mini_attr_tuple = tuple(mini_dim_attributes)
        IdentifierValidator.validate_columns("mini_dim_attributes", mini_attr_tuple)
        src_key_tuple = (
            tuple(source_key_columns)
            if source_key_columns is not None
            else main_key_tuple
        )
        IdentifierValidator.validate_columns("source_key_columns", src_key_tuple)
        self._source_pool = source_pool
        self._source_query = source_query
        self._main_pool = main_pool
        self._main_table = main_table
        self._main_key_columns = main_key_tuple
        self._fact_fk_column = fact_fk_column
        self._mini_pool = mini_pool
        self._mini_table = mini_table
        self._mini_dim_attributes = mini_attr_tuple
        self._mini_dim_key_column = mini_dim_key_column
        self._source_key_columns = src_key_tuple
        self._source_columns = src_key_tuple + mini_attr_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def lookup_mini_dim_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._mini_dim_attributes)
        return (
            f"SELECT {self._mini_dim_key_column} FROM {self._mini_table} "
            f"WHERE {where}"
        )

    @property
    def insert_mini_dim_query(self) -> str:
        cols = ", ".join(self._mini_dim_attributes)
        placeholders = ", ".join(["?"] * len(self._mini_dim_attributes))
        return (
            f"INSERT INTO {self._mini_table} ({cols}) VALUES ({placeholders})"
        )

    @property
    def last_insert_rowid_query(self) -> str:
        return "SELECT last_insert_rowid()"

    @property
    def update_main_fk_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._main_key_columns)
        return (
            f"UPDATE {self._main_table} SET {self._fact_fk_column} = ? "
            f"WHERE {where}"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Resolve mini-dimension keys for each source row, inserting new mini-dim rows as needed, then update the main dimension FK.

        Returns:
            A dict with keys ``succeeded``, ``main_table``, ``mini_table``,
            ``mini_dim_reused``, and ``mini_dim_inserted`` summarising the outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        mini_dim_reused = 0
        mini_dim_inserted = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            key_values = tuple(row_dict[k] for k in self._source_key_columns)
            attr_values = tuple(
                row_dict[k] for k in self._mini_dim_attributes
            )
            existing = await self._mini_pool.fetch_all(
                self.lookup_mini_dim_query, attr_values
            )
            if existing:
                mini_sk = existing[0][0]
                mini_dim_reused += 1
            else:
                await self._mini_pool.execute(
                    self.insert_mini_dim_query, attr_values
                )
                rowid_rows = await self._mini_pool.fetch_all(
                    self.last_insert_rowid_query
                )
                mini_sk = rowid_rows[0][0]
                mini_dim_inserted += 1
            main_key_values = tuple(
                row_dict.get(k, key_values[i])
                for i, k in enumerate(self._main_key_columns)
            )
            await self._main_pool.execute(
                self.update_main_fk_query,
                (mini_sk,) + main_key_values,
            )
        return {
            "succeeded": True,
            "main_table": self._main_table,
            "mini_table": self._mini_table,
            "mini_dim_reused": mini_dim_reused,
            "mini_dim_inserted": mini_dim_inserted,
        }
