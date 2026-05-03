"""``DataVaultPITTableBuilder`` — Point-In-Time table builder for Data Vault.

A Point-In-Time (PIT) table materialises one row per Hub member per
snapshot date.  Each row holds a pointer (the satellite ``load_date``) to
the satellite row that was **current as of** that snapshot date for each
registered satellite.

Behaviour
---------
For each ``(hub_hash_key, snapshot_date)`` pair produced by
``pit_spine_query``:

For every satellite registered in ``satellite_configs``:

* Find the satellite row whose ``load_date <= snapshot_date`` and
  ``(load_end_date > snapshot_date OR load_end_date IS NULL)``.
  That row's ``load_date`` is the **as-of pointer** stored in the PIT.
* If no satellite row exists for that key / date combination the
  pointer column stores ``NULL``.

The PIT table is **truncated and rebuilt** on every run (snapshot tables
are not append-only; they represent a full re-materialisation).

``satellite_configs`` is a sequence of dicts with keys:

* ``"table"`` — satellite table name (validated identifier)
* ``"hub_hash_key_column"`` — FK column in the satellite pointing back to
  the Hub hash key
* ``"load_date_column"`` — open-interval start column (defaults
  ``"load_date"`` when absent)
* ``"load_end_date_column"`` — open-interval end column (defaults
  ``"load_end_date"`` when absent)
* ``"pit_pointer_column"`` — column name to write the pointer into the PIT
  table (validated identifier)
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DataVaultPITTableBuilder(SubTapestry):
    """Rebuild a Point-In-Time table for one Hub across all its Satellites."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        pit_spine_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        hub_hash_key_column: str,
        snapshot_date_column: str,
        satellite_configs: Sequence[dict[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._source_pool = source_pool
        self._pit_spine_query = pit_spine_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._hub_hash_key_column = hub_hash_key_column
        self._snapshot_date_column = snapshot_date_column
        self._satellite_configs = validated_sat_configs
        super().__init__(_config=_config, **kwargs)

    def _as_of_query(self, sat: dict[str, str]) -> str:
        return (
            f"SELECT {sat['load_date_column']} FROM {sat['table']} "
            f"WHERE {sat['hub_hash_key_column']} = ? "
            f"AND {sat['load_date_column']} <= ? "
            f"AND ({sat['load_end_date_column']} > ? "
            f"OR {sat['load_end_date_column']} IS NULL) "
            f"ORDER BY {sat['load_date_column']} DESC LIMIT 1"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Truncate and rebuild the PIT table for all hub members and snapshot dates.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and ``rows_written``
            summarising the build outcome.
        """
        await self._target_pool.execute(f"DELETE FROM {self._target_table}")
        spine_rows = await self._source_pool.fetch_all(self._pit_spine_query)
        pointer_columns = [s["pit_pointer_column"] for s in self._satellite_configs]
        all_cols = (
            [self._hub_hash_key_column, self._snapshot_date_column] + pointer_columns
        )
        col_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        insert_sql = (
            f"INSERT INTO {self._target_table} ({col_list}) VALUES ({placeholders})"
        )
        rows_written = 0
        for spine_row in spine_rows:
            hub_hk, snapshot_date = spine_row[0], spine_row[1]
            pointers: list[Any] = []
            for sat in self._satellite_configs:
                as_of_rows = await self._source_pool.fetch_all(
                    self._as_of_query(sat),
                    (hub_hk, snapshot_date, snapshot_date),
                )
                pointers.append(as_of_rows[0][0] if as_of_rows else None)
            await self._target_pool.execute(
                insert_sql,
                (hub_hk, snapshot_date) + tuple(pointers),
            )
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_written": rows_written,
        }
