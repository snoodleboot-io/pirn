"""``DataVaultPITTableBuilder`` — Point-In-Time table builder for Data Vault.

A Point-In-Time (PIT) table materialises one row per Hub member per
snapshot date.  Each row holds a pointer (the satellite ``load_date``) to
the satellite row that was **current as of** that snapshot date for each
registered satellite.

Algorithm:
    1. Receive resolved ``source_pool``, ``pit_spine_query``, ``target_pool``,
       ``target_table``, ``hub_hash_key_column``, ``snapshot_date_column``,
       and ``satellite_configs`` in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and required keys in each satellite config dict.
    3. Truncate the target PIT table (DELETE FROM).
    4. Fetch the spine rows (hub hash key + snapshot date) via
       ``source_pool.fetch_all(pit_spine_query)``.
    5. For each (hub_hash_key, snapshot_date) pair and each satellite, find
       the satellite row whose ``load_date <= snapshot_date`` and
       ``(load_end_date > snapshot_date OR load_end_date IS NULL)``.
    6. Store that row's ``load_date`` as the as-of pointer (NULL if no row
       matches).
    7. INSERT one PIT row per spine row.
    8. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_written``.

References:
    [1] Linstedt & Olschimke — *Building a Scalable Data Warehouse with Data Vault 2.0*
        (2015), Chapter 10: Point-In-Time tables.
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


class DataVaultPITTableBuilder(Knot):
    """Rebuild a Point-In-Time table for one Hub across all its Satellites."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        pit_spine_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        hub_hash_key_column: Knot | str,
        snapshot_date_column: Knot | str,
        satellite_configs: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            pit_spine_query=pit_spine_query,
            target_pool=target_pool,
            target_table=target_table,
            hub_hash_key_column=hub_hash_key_column,
            snapshot_date_column=snapshot_date_column,
            satellite_configs=satellite_configs,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _as_of_query(sat: dict[str, str]) -> str:
        return (
            f"SELECT {sat['load_date_column']} FROM {sat['table']} "
            f"WHERE {sat['hub_hash_key_column']} = ? "
            f"AND {sat['load_date_column']} <= ? "
            f"AND ({sat['load_end_date_column']} > ? "
            f"OR {sat['load_end_date_column']} IS NULL) "
            f"ORDER BY {sat['load_date_column']} DESC LIMIT 1"
        )

    async def process(
        self,
        *,
        source_pool: Any,
        pit_spine_query: Any,
        target_pool: Any,
        target_table: Any,
        hub_hash_key_column: Any,
        snapshot_date_column: Any,
        satellite_configs: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultPITTableBuilder: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultPITTableBuilder: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("pit_spine_query", pit_spine_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DataVaultPITTableBuilder: {label} must be a non-empty string"
                )
        for label, value in (
            ("hub_hash_key_column", hub_hash_key_column),
            ("snapshot_date_column", snapshot_date_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DataVaultPITTableBuilder: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("hub_hash_key_column", hub_hash_key_column)
        IdentifierValidator.validate_column("snapshot_date_column", snapshot_date_column)
        if not satellite_configs:
            raise ValueError(
                "DataVaultPITTableBuilder: satellite_configs must be non-empty"
            )
        validated_sat_configs: list[dict[str, str]] = []
        for idx, cfg in enumerate(satellite_configs):
            for required_key in ("table", "hub_hash_key_column", "pit_pointer_column"):
                if required_key not in cfg or not cfg[required_key]:
                    raise ValueError(
                        f"DataVaultPITTableBuilder: satellite_configs[{idx}] "
                        f"missing required key {required_key!r}"
                    )
            IdentifierValidator.validate_column(
                f"satellite_configs[{idx}].table", cfg["table"]
            )
            IdentifierValidator.validate_column(
                f"satellite_configs[{idx}].hub_hash_key_column",
                cfg["hub_hash_key_column"],
            )
            IdentifierValidator.validate_column(
                f"satellite_configs[{idx}].pit_pointer_column",
                cfg["pit_pointer_column"],
            )
            load_date_col = cfg.get("load_date_column", "load_date")
            load_end_date_col = cfg.get("load_end_date_column", "load_end_date")
            IdentifierValidator.validate_column(
                f"satellite_configs[{idx}].load_date_column", load_date_col
            )
            IdentifierValidator.validate_column(
                f"satellite_configs[{idx}].load_end_date_column", load_end_date_col
            )
            validated_sat_configs.append(
                {
                    "table": cfg["table"],
                    "hub_hash_key_column": cfg["hub_hash_key_column"],
                    "load_date_column": load_date_col,
                    "load_end_date_column": load_end_date_col,
                    "pit_pointer_column": cfg["pit_pointer_column"],
                }
            )
        await target_pool.execute(f"DELETE FROM {target_table}")
        spine_rows = await source_pool.fetch_all(pit_spine_query)
        pointer_columns = [s["pit_pointer_column"] for s in validated_sat_configs]
        all_cols = [hub_hash_key_column, snapshot_date_column, *pointer_columns]
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        insert_sql = (
            f"INSERT INTO {target_table} ({col_list}) VALUES ({placeholders})"
        )
        rows_written = 0
        for spine_row in spine_rows:
            hub_hk, snapshot_date = spine_row[0], spine_row[1]
            pointers: list[Any] = []
            for sat in validated_sat_configs:
                as_of_rows = await source_pool.fetch_all(
                    DataVaultPITTableBuilder._as_of_query(sat),
                    (hub_hk, snapshot_date, snapshot_date),
                )
                pointers.append(as_of_rows[0][0] if as_of_rows else None)
            await target_pool.execute(
                insert_sql,
                (hub_hk, snapshot_date, *pointers),
            )
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_written": rows_written,
        }
