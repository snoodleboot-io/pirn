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

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, look up the mini-dim table by attribute values.
    4. If found, reuse the existing surrogate key.
    5. If not found, insert a new mini-dim row and retrieve the surrogate via
       ``last_insert_rowid()``.
    6. Update the main-dim row's FK column with the resolved surrogate key.
    7. Return a summary dict with ``mini_dim_reused`` and ``mini_dim_inserted``.

References:
    [1] Kimball Group — SCD Type 4 (mini-dimension):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-4/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType4MiniDimension(Knot):
    """Split rapidly-changing attributes into a mini-dimension table (SCD Type 4)."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        main_pool: Knot | DatabaseConnectionPool,
        main_table: Knot | str,
        main_key_columns: Knot | tuple[str, ...],
        fact_fk_column: Knot | str,
        mini_pool: Knot | DatabaseConnectionPool,
        mini_table: Knot | str,
        mini_dim_attributes: Knot | tuple[str, ...],
        mini_dim_key_column: Knot | str = "mini_dim_sk",
        source_key_columns: Knot | tuple[str, ...] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            main_pool=main_pool,
            main_table=main_table,
            main_key_columns=main_key_columns,
            fact_fk_column=fact_fk_column,
            mini_pool=mini_pool,
            mini_table=mini_table,
            mini_dim_attributes=mini_dim_attributes,
            mini_dim_key_column=mini_dim_key_column,
            source_key_columns=source_key_columns,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _lookup_mini_dim_query(
        mini_table: str, mini_dim_attributes: tuple[str, ...], mini_dim_key_column: str
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in mini_dim_attributes)
        return f"SELECT {mini_dim_key_column} FROM {mini_table} WHERE {where}"

    @staticmethod
    def _insert_mini_dim_query(mini_table: str, mini_dim_attributes: tuple[str, ...]) -> str:
        cols = ", ".join(mini_dim_attributes)
        placeholders = ", ".join(["?"] * len(mini_dim_attributes))
        return f"INSERT INTO {mini_table} ({cols}) VALUES ({placeholders})"

    @staticmethod
    def _update_main_fk_query(
        main_table: str, fact_fk_column: str, main_key_columns: tuple[str, ...]
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in main_key_columns)
        return f"UPDATE {main_table} SET {fact_fk_column} = ? WHERE {where}"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        main_pool: Any,
        main_table: Any,
        main_key_columns: Any,
        fact_fk_column: Any,
        mini_pool: Any,
        mini_table: Any,
        mini_dim_attributes: Any,
        mini_dim_key_column: Any = "mini_dim_sk",
        source_key_columns: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        for label, pool in (
            ("source_pool", source_pool),
            ("main_pool", main_pool),
            ("mini_pool", mini_pool),
        ):
            if not isinstance(pool, DatabaseConnectionPool):
                raise TypeError(f"ScdType4MiniDimension: {label} must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType4MiniDimension: source_query must be a non-empty string")
        for label, value in (
            ("main_table", main_table),
            ("mini_table", mini_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ScdType4MiniDimension: {label} must be a non-empty string")
        IdentifierValidator.validate_column("main_table", main_table)
        IdentifierValidator.validate_column("mini_table", mini_table)
        IdentifierValidator.validate_column("fact_fk_column", fact_fk_column)
        IdentifierValidator.validate_column("mini_dim_key_column", mini_dim_key_column)
        main_key_tuple = tuple(main_key_columns)
        IdentifierValidator.validate_columns("main_key_columns", main_key_tuple)
        mini_attr_tuple = tuple(mini_dim_attributes)
        IdentifierValidator.validate_columns("mini_dim_attributes", mini_attr_tuple)
        src_key_tuple = (
            tuple(source_key_columns) if source_key_columns is not None else main_key_tuple
        )
        IdentifierValidator.validate_columns("source_key_columns", src_key_tuple)
        source_columns = src_key_tuple + mini_attr_tuple
        lookup_q = ScdType4MiniDimension._lookup_mini_dim_query(
            mini_table, mini_attr_tuple, mini_dim_key_column
        )
        insert_mini_q = ScdType4MiniDimension._insert_mini_dim_query(mini_table, mini_attr_tuple)
        update_main_q = ScdType4MiniDimension._update_main_fk_query(
            main_table, fact_fk_column, main_key_tuple
        )
        source_rows = await source_pool.fetch_all(source_query)
        mini_dim_reused = 0
        mini_dim_inserted = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in src_key_tuple)
            attr_values = tuple(row_dict[k] for k in mini_attr_tuple)
            existing = await mini_pool.fetch_all(lookup_q, attr_values)
            if existing:
                mini_sk = existing[0][0]
                mini_dim_reused += 1
            else:
                await mini_pool.execute(insert_mini_q, attr_values)
                rowid_rows = await mini_pool.fetch_all("SELECT last_insert_rowid()")
                mini_sk = rowid_rows[0][0]
                mini_dim_inserted += 1
            main_key_values = tuple(
                row_dict.get(k, key_values[i]) for i, k in enumerate(main_key_tuple)
            )
            await main_pool.execute(update_main_q, (mini_sk, *main_key_values))
        return {
            "succeeded": True,
            "main_table": main_table,
            "mini_table": mini_table,
            "mini_dim_reused": mini_dim_reused,
            "mini_dim_inserted": mini_dim_inserted,
        }
