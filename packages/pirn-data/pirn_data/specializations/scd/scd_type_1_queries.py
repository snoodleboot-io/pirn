"""``ScdType1Queries`` — parameterised SQL for the SCD Type 1 (overwrite) merge.

Shared by :class:`ScdType1` and :class:`ScdType1MergeKnot`, which issue
the same statements against a target pool. Every builder splices already-validated identifiers
(:class:`~pirn_data.identifier_validator.IdentifierValidator`) and leaves
values as ``?`` placeholders for the pool to bind.
"""

from __future__ import annotations


class ScdType1Queries:
    """Static SQL builders for the SCD Type 1 (overwrite) merge."""

    @staticmethod
    def select_query(target_table: str, column_names: tuple[str, ...]) -> str:
        column_list = ", ".join(column_names)
        return f"SELECT {column_list} FROM {target_table}"

    @staticmethod
    def insert_query(target_table: str, column_names: tuple[str, ...]) -> str:
        column_list = ", ".join(column_names)
        placeholders = ", ".join(["?"] * len(column_names))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def update_query(
        target_table: str,
        primary_keys: tuple[str, ...],
        non_key_columns: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where_clause}"
