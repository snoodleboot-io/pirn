"""``DataVaultBridgeTableBuilder`` — Bridge table builder for Data Vault.

A Bridge table **pre-joins** one or more Links and their associated Hubs
into a flat foreign-key structure that BI tools expecting a star schema
can consume directly.  Each row in the Bridge corresponds to one
relationship instance and carries the natural business keys (or surrogate
IDs) from every participating Hub alongside the Link's own hash key.

The Bridge is a **derived** table: it is truncated and rebuilt on every
run from the Link and Hub tables in the vault.

Configuration
-------------
``hub_configs`` is a sequence of dicts, one per Hub that participates in
the Link:

* ``"hub_table"`` — Hub table name (validated identifier)
* ``"hub_hash_key_column"`` — PK of the Hub (validated identifier)
* ``"link_fk_column"`` — FK column in the Link table pointing to this Hub
  (validated identifier)
* ``"bridge_columns"`` — list of column names to carry from the Hub into
  the Bridge row (each validated)

The Link itself is identified by ``link_table`` and
``link_hash_key_column``.  The Bridge row always includes
``link_hash_key_column`` as its own column.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DataVaultBridgeTableBuilder(SubTapestry):
    """Rebuild a Bridge table by flattening a Link + Hub chain into star-schema FKs."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        link_table: str,
        link_hash_key_column: str,
        hub_configs: Sequence[dict[str, Any]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
                raise ValueError(
                    f"DataVaultBridgeTableBuilder: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("link_table", link_table)
        IdentifierValidator.validate_column("link_hash_key_column", link_hash_key_column)
        if not hub_configs:
            raise ValueError(
                "DataVaultBridgeTableBuilder: hub_configs must be non-empty"
            )
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
            IdentifierValidator.validate_column(
                f"hub_configs[{idx}].hub_table", cfg["hub_table"]
            )
            IdentifierValidator.validate_column(
                f"hub_configs[{idx}].hub_hash_key_column", cfg["hub_hash_key_column"]
            )
            IdentifierValidator.validate_column(
                f"hub_configs[{idx}].link_fk_column", cfg["link_fk_column"]
            )
            bridge_cols = list(cfg["bridge_columns"])
            IdentifierValidator.validate_columns(
                f"hub_configs[{idx}].bridge_columns", bridge_cols
            )
            validated_hub_configs.append(
                {
                    "hub_table": cfg["hub_table"],
                    "hub_hash_key_column": cfg["hub_hash_key_column"],
                    "link_fk_column": cfg["link_fk_column"],
                    "bridge_columns": bridge_cols,
                }
            )
        self._source_pool = source_pool
        self._target_pool = target_pool
        self._target_table = target_table
        self._link_table = link_table
        self._link_hash_key_column = link_hash_key_column
        self._hub_configs = validated_hub_configs
        super().__init__(_config=_config, **kwargs)

    def _hub_lookup_query(self, hub_cfg: dict[str, Any]) -> str:
        cols = ", ".join(hub_cfg["bridge_columns"])
        return (
            f"SELECT {cols} FROM {hub_cfg['hub_table']} "
            f"WHERE {hub_cfg['hub_hash_key_column']} = ?"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Truncate and rebuild the Bridge table from the Link and Hub tables.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and ``rows_written``
            summarising the build outcome.
        """
        await self._target_pool.execute(f"DELETE FROM {self._target_table}")
        link_rows = await self._source_pool.fetch_all(
            f"SELECT {self._link_hash_key_column}, "
            + ", ".join(c["link_fk_column"] for c in self._hub_configs)
            + f" FROM {self._link_table}"
        )
        all_bridge_cols = [self._link_hash_key_column]
        for hub_cfg in self._hub_configs:
            all_bridge_cols.extend(hub_cfg["bridge_columns"])
        col_list = ", ".join(all_bridge_cols)
        placeholders = ", ".join(["?"] * len(all_bridge_cols))
        insert_sql = (
            f"INSERT INTO {self._target_table} ({col_list}) VALUES ({placeholders})"
        )
        rows_written = 0
        for link_row in link_rows:
            link_hk = link_row[0]
            hub_fk_values = link_row[1:]
            bridge_values: list[Any] = [link_hk]
            for hub_cfg, hub_fk in zip(self._hub_configs, hub_fk_values):
                hub_rows = await self._source_pool.fetch_all(
                    self._hub_lookup_query(hub_cfg), (hub_fk,)
                )
                if hub_rows:
                    bridge_values.extend(hub_rows[0])
                else:
                    bridge_values.extend([None] * len(hub_cfg["bridge_columns"]))
            await self._target_pool.execute(insert_sql, tuple(bridge_values))
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_written": rows_written,
        }
