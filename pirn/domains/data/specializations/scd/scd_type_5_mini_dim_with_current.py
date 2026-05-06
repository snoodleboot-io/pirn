"""``ScdType5MiniDimWithCurrent`` — Slowly Changing Dimension Type 5.

SCD Type 5 extends Type 4 by adding a denormalized ``current_mini_dim_sk``
column directly on the main dimension table. This allows queries to join
the current mini-dimension values without needing the fact table as an
intermediary.

Behaviour
---------
For each row from ``source_query``:

1. Look up the mini-dimension table by ``mini_dim_attributes`` values.
2. Reuse the existing mini-dim key or insert a new mini-dim row.
3. Update the main dimension's ``fact_fk_column`` (used on the fact table).
4. Additionally, update the main dimension's ``current_mini_dim_sk_column``
   to the current mini-dim surrogate key so that the main dim row always
   carries a direct reference to the current mini-dim profile.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, look up the mini-dim table by attribute values.
    4. If found, reuse the existing surrogate key.
    5. If not found, insert a new mini-dim row and retrieve the surrogate via
       ``last_insert_rowid()``.
    6. Update the main-dim row's ``fact_fk_column`` and
       ``current_mini_dim_sk_column`` with the resolved surrogate key.
    7. Return a summary dict with ``mini_dim_reused`` and ``mini_dim_inserted``.

References:
    [1] Kimball Group — SCD Type 5 (mini-dimension + current outrigger):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-5/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType5MiniDimWithCurrent(Knot):
    """Type 4 mini-dimension plus a denormalized current_mini_dim_sk on the main dimension."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        main_pool: Knot | DatabaseConnectionPool,
        main_table: Knot | str,
        main_key_columns: Knot | tuple[str, ...],
        fact_fk_column: Knot | str,
        current_mini_dim_sk_column: Knot | str,
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
            current_mini_dim_sk_column=current_mini_dim_sk_column,
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
    def _update_main_query(
        main_table: str,
        fact_fk_column: str,
        current_mini_dim_sk_column: str,
        main_key_columns: tuple[str, ...],
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in main_key_columns)
        return (
            f"UPDATE {main_table} "
            f"SET {fact_fk_column} = ?, {current_mini_dim_sk_column} = ? "
            f"WHERE {where}"
        )

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        main_pool: Any,
        main_table: Any,
        main_key_columns: Any,
        fact_fk_column: Any,
        current_mini_dim_sk_column: Any,
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
                raise TypeError(
                    f"ScdType5MiniDimWithCurrent: {label} must be a DatabaseConnectionPool"
                )
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType5MiniDimWithCurrent: source_query must be a non-empty string")
        for label, value in (
            ("main_table", main_table),
            ("mini_table", mini_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ScdType5MiniDimWithCurrent: {label} must be a non-empty string")
        IdentifierValidator.validate_column("main_table", main_table)
        IdentifierValidator.validate_column("mini_table", mini_table)
        IdentifierValidator.validate_column("fact_fk_column", fact_fk_column)
        IdentifierValidator.validate_column(
            "current_mini_dim_sk_column", current_mini_dim_sk_column
        )
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
        lookup_q = ScdType5MiniDimWithCurrent._lookup_mini_dim_query(
            mini_table, mini_attr_tuple, mini_dim_key_column
        )
        insert_mini_q = ScdType5MiniDimWithCurrent._insert_mini_dim_query(
            mini_table, mini_attr_tuple
        )
        update_main_q = ScdType5MiniDimWithCurrent._update_main_query(
            main_table, fact_fk_column, current_mini_dim_sk_column, main_key_tuple
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
            await main_pool.execute(update_main_q, (mini_sk, mini_sk, *main_key_values))
        return {
            "succeeded": True,
            "main_table": main_table,
            "mini_table": mini_table,
            "mini_dim_reused": mini_dim_reused,
            "mini_dim_inserted": mini_dim_inserted,
        }
