"""``ScdType2Queries`` — parameterised SQL for the SCD Type 2 (history rows) merge.

Shared by :class:`ScdType2` and :class:`ScdType2MergeKnot`, which issue
the same statements against a target pool. Every builder splices already-validated identifiers
(:class:`~pirn_data.identifier_validator.IdentifierValidator`) and leaves
values as ``?`` placeholders for the pool to bind.
"""

from __future__ import annotations


class ScdType2Queries:
    """Static SQL builders for the SCD Type 2 (history rows) merge."""

    @staticmethod
    def select_query(
        target_table: str, column_names: tuple[str, ...], current_flag_column: str
    ) -> str:
        column_list = ", ".join(column_names)
        return f"SELECT {column_list} FROM {target_table} WHERE {current_flag_column} = 1"

    @staticmethod
    def insert_query(
        target_table: str,
        column_names: tuple[str, ...],
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [*column_names, effective_date_column, expiry_date_column, current_flag_column]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def expire_query(
        target_table: str,
        primary_keys: tuple[str, ...],
        expiry_date_column: str,
        current_flag_column: str,
    ) -> str:
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return (
            f"UPDATE {target_table} SET "
            f"{expiry_date_column} = ?, "
            f"{current_flag_column} = 0 "
            f"WHERE {where_clause} AND {current_flag_column} = 1"
        )
