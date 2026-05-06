"""``DataVaultBridgeTableBuilder`` — Bridge table builder for Data Vault.

A Bridge table **pre-joins** one or more Links and their associated Hubs
into a flat foreign-key structure that BI tools expecting a star schema
can consume directly.  Each row in the Bridge corresponds to one
relationship instance and carries the natural business keys (or surrogate
IDs) from every participating Hub alongside the Link's own hash key.

The Bridge is a **derived** table: it is truncated and rebuilt on every
run from the Link and Hub tables in the vault.

Algorithm:
    1. Receive resolved ``source_pool``, ``target_pool``, ``target_table``,
       ``link_table``, ``link_hash_key_column``, and ``hub_configs``
       in ``process()``.
    2. Validate all inputs: pool types, non-empty strings, identifier safety,
       and required keys in each hub config dict.
    3. Truncate the target Bridge table (DELETE FROM).
    4. Fetch all rows from the Link table.
    5. For each Link row, look up each participating Hub by its FK value and
       gather the configured bridge columns.
    6. INSERT one Bridge row per Link row (NULL-filling any missing Hub rows).
    7. Return a summary dict with ``succeeded``, ``target_table``,
       and ``rows_written``.

References:
    [1] Linstedt & Olschimke — *Building a Scalable Data Warehouse with Data Vault 2.0*
        (2015), Chapter 9: Bridge tables.
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


class DataVaultBridgeTableBuilder(Knot):
    """Rebuild a Bridge table by flattening a Link + Hub chain into star-schema FKs."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        link_table: Knot | str,
        link_hash_key_column: Knot | str,
        hub_configs: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            target_pool=target_pool,
            target_table=target_table,
            link_table=link_table,
            link_hash_key_column=link_hash_key_column,
            hub_configs=hub_configs,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _hub_lookup_query(hub_cfg: dict[str, Any]) -> str:
        cols = ", ".join(hub_cfg["bridge_columns"])
        return (
            f"SELECT {cols} FROM {hub_cfg['hub_table']} WHERE {hub_cfg['hub_hash_key_column']} = ?"
        )

    async def process(
        self,
        *,
        source_pool: Any,
        target_pool: Any,
        target_table: Any,
        link_table: Any,
        link_hash_key_column: Any,
        hub_configs: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultBridgeTableBuilder: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DataVaultBridgeTableBuilder: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("target_table", target_table),
            ("link_table", link_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"DataVaultBridgeTableBuilder: {label} must be a non-empty string")
        if not isinstance(link_hash_key_column, str) or not link_hash_key_column:
            raise ValueError(
                "DataVaultBridgeTableBuilder: link_hash_key_column must be a non-empty string"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("link_table", link_table)
        IdentifierValidator.validate_column("link_hash_key_column", link_hash_key_column)
        if not hub_configs:
            raise ValueError("DataVaultBridgeTableBuilder: hub_configs must be non-empty")
        validated_hub_configs: list[dict[str, Any]] = []
        for idx, cfg in enumerate(hub_configs):
            for required_key in (
                "hub_table",
                "hub_hash_key_column",
                "link_fk_column",
                "bridge_columns",
            ):
                if required_key not in cfg or not cfg[required_key]:
                    raise ValueError(
                        f"DataVaultBridgeTableBuilder: hub_configs[{idx}] "
                        f"missing required key {required_key!r}"
                    )
            IdentifierValidator.validate_column(f"hub_configs[{idx}].hub_table", cfg["hub_table"])
            IdentifierValidator.validate_column(
                f"hub_configs[{idx}].hub_hash_key_column", cfg["hub_hash_key_column"]
            )
            IdentifierValidator.validate_column(
                f"hub_configs[{idx}].link_fk_column", cfg["link_fk_column"]
            )
            bridge_cols = list(cfg["bridge_columns"])
            IdentifierValidator.validate_columns(f"hub_configs[{idx}].bridge_columns", bridge_cols)
            validated_hub_configs.append(
                {
                    "hub_table": cfg["hub_table"],
                    "hub_hash_key_column": cfg["hub_hash_key_column"],
                    "link_fk_column": cfg["link_fk_column"],
                    "bridge_columns": bridge_cols,
                }
            )
        await target_pool.execute(f"DELETE FROM {target_table}")
        link_rows = await source_pool.fetch_all(
            f"SELECT {link_hash_key_column}, "
            + ", ".join(c["link_fk_column"] for c in validated_hub_configs)
            + f" FROM {link_table}"
        )
        all_bridge_cols = [link_hash_key_column]
        for hub_cfg in validated_hub_configs:
            all_bridge_cols.extend(hub_cfg["bridge_columns"])
        col_list = ", ".join(all_bridge_cols)
        placeholders = ", ".join(["?"] * len(all_bridge_cols))
        insert_sql = f"INSERT INTO {target_table} ({col_list}) VALUES ({placeholders})"
        rows_written = 0
        for link_row in link_rows:
            link_hk = link_row[0]
            hub_fk_values = link_row[1:]
            bridge_values: list[Any] = [link_hk]
            for hub_cfg, hub_fk in zip(validated_hub_configs, hub_fk_values, strict=False):
                hub_rows = await source_pool.fetch_all(
                    DataVaultBridgeTableBuilder._hub_lookup_query(hub_cfg), (hub_fk,)
                )
                if hub_rows:
                    bridge_values.extend(hub_rows[0])
                else:
                    bridge_values.extend([None] * len(hub_cfg["bridge_columns"]))
            await target_pool.execute(insert_sql, tuple(bridge_values))
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_written": rows_written,
        }
