"""``ScdType7Queries`` — parameterised SQL for the SCD Type 7 merge.

Type 7 keeps effective-dated history rows keyed by a surrogate key, optionally
mirroring each non-key column's current value onto every row of the key. Every
builder splices already-validated identifiers
(:class:`~pirn_data.identifier_validator.IdentifierValidator`) and leaves values
as ``?`` placeholders for the pool to bind.
"""

from __future__ import annotations


class ScdType7Queries:
    """Static SQL builders for the SCD Type 7 merge."""

    @staticmethod
    def select_query(
        target_table: str, column_names: tuple[str, ...], current_flag_column: str
    ) -> str:
        """Select the current row per key."""
        column_list = ", ".join(column_names)
        return f"SELECT {column_list} FROM {target_table} WHERE {current_flag_column} = 1"

    @staticmethod
    def max_surrogate_query(target_table: str, surrogate_key_column: str) -> str:
        """Read the highest surrogate key already allocated."""
        return f"SELECT COALESCE(MAX({surrogate_key_column}), 0) FROM {target_table}"

    @staticmethod
    def insert_query(
        target_table: str,
        surrogate_key_column: str,
        column_names: tuple[str, ...],
        effective_date_column: str,
        expiry_date_column: str,
        current_flag_column: str,
        mirror_columns: tuple[str, ...] | None = None,
    ) -> str:
        """Insert a new surrogate-keyed version, optionally with its mirror columns."""
        all_cols = [
            surrogate_key_column,
            *column_names,
            effective_date_column,
            expiry_date_column,
            current_flag_column,
        ]
        if mirror_columns is not None:
            all_cols.extend(mirror_columns)
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
        """Close out the current row for a key."""
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return (
            f"UPDATE {target_table} SET "
            f"{expiry_date_column} = ?, "
            f"{current_flag_column} = 0 "
            f"WHERE {where_clause} AND {current_flag_column} = 1"
        )

    @staticmethod
    def backfill_current_query(
        target_table: str,
        primary_keys: tuple[str, ...],
        mirror_columns: tuple[str, ...],
    ) -> str:
        """Push the new current values onto every historical row of a key."""
        set_clause = ", ".join(f"{c} = ?" for c in mirror_columns)
        where_clause = " AND ".join(f"{k} = ?" for k in primary_keys)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where_clause}"
