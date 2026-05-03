"""Tests for :class:`DataVaultPITTableBuilder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_pit_table_builder import (
    DataVaultPITTableBuilder,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def vault_pool() -> SqlitePool:
    """Single pool holding the spine, satellite, and PIT tables."""
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE pit_spine ("
        "  hub_hk TEXT NOT NULL,"
        "  snapshot_date TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO pit_spine (hub_hk, snapshot_date) VALUES (?, ?)",
        [
            ("hk_1", "2026-01-01"),
            ("hk_1", "2026-02-01"),
            ("hk_2", "2026-01-01"),
        ],
    )
    await pool.execute(
        "CREATE TABLE sat_customer ("
        "  hub_hk TEXT NOT NULL,"
        "  hash_diff TEXT NOT NULL,"
        "  load_date TEXT NOT NULL,"
        "  load_end_date TEXT"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO sat_customer (hub_hk, hash_diff, load_date, load_end_date) VALUES (?, ?, ?, ?)",
        [
            ("hk_1", "diff_a", "2025-12-01", "2026-01-15"),
            ("hk_1", "diff_b", "2026-01-15", None),
            ("hk_2", "diff_c", "2025-11-01", None),
        ],
    )
    await pool.execute(
        "CREATE TABLE pit_customer ("
        "  hub_hk TEXT NOT NULL,"
        "  snapshot_date TEXT NOT NULL,"
        "  sat_customer_load_date TEXT"
        ")"
    )
    yield pool
    await pool.close()


_SAT_CFG = [
    {
        "table": "sat_customer",
        "hub_hash_key_column": "hub_hk",
        "load_date_column": "load_date",
        "load_end_date_column": "load_end_date",
        "pit_pointer_column": "sat_customer_load_date",
    }
]


class TestConstruction:
    def test_rejects_non_pool_source(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            with Tapestry():
                DataVaultPITTableBuilder(
                    source_pool="bad",  # type: ignore[arg-type]
                    pit_spine_query="SELECT 1",
                    target_pool=pool,
                    target_table="pit_customer",
                    hub_hash_key_column="hub_hk",
                    snapshot_date_column="snapshot_date",
                    satellite_configs=_SAT_CFG,
                    _config=KnotConfig(id="pit"),
                )

    def test_rejects_empty_satellite_configs(self, vault_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="satellite_configs"):
            with Tapestry():
                DataVaultPITTableBuilder(
                    source_pool=vault_pool,
                    pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine",
                    target_pool=vault_pool,
                    target_table="pit_customer",
                    hub_hash_key_column="hub_hk",
                    snapshot_date_column="snapshot_date",
                    satellite_configs=[],
                    _config=KnotConfig(id="pit"),
                )

    def test_rejects_sat_config_missing_required_key(
        self, vault_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="missing required key"):
            with Tapestry():
                DataVaultPITTableBuilder(
                    source_pool=vault_pool,
                    pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine",
                    target_pool=vault_pool,
                    target_table="pit_customer",
                    hub_hash_key_column="hub_hk",
                    snapshot_date_column="snapshot_date",
                    satellite_configs=[{"table": "sat_customer"}],
                    _config=KnotConfig(id="pit"),
                )

    def test_rejects_invalid_target_table(self, vault_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            with Tapestry():
                DataVaultPITTableBuilder(
                    source_pool=vault_pool,
                    pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine",
                    target_pool=vault_pool,
                    target_table="bad; DROP TABLE x",
                    hub_hash_key_column="hub_hk",
                    snapshot_date_column="snapshot_date",
                    satellite_configs=_SAT_CFG,
                    _config=KnotConfig(id="pit"),
                )


@pytest.mark.asyncio
class TestPITTableBuilderBehaviour:
    async def test_builds_pit_rows_for_all_spine_entries(
        self, vault_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DataVaultPITTableBuilder(
                source_pool=vault_pool,
                pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine ORDER BY hub_hk, snapshot_date",
                target_pool=vault_pool,
                target_table="pit_customer",
                hub_hash_key_column="hub_hk",
                snapshot_date_column="snapshot_date",
                satellite_configs=_SAT_CFG,
                _config=KnotConfig(id="pit_build"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await vault_pool.fetch_all(
            "SELECT hub_hk, snapshot_date, sat_customer_load_date "
            "FROM pit_customer ORDER BY hub_hk, snapshot_date"
        )
        assert len(rows) == 3

    async def test_pointer_resolves_correct_as_of_version(
        self, vault_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DataVaultPITTableBuilder(
                source_pool=vault_pool,
                pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine ORDER BY hub_hk, snapshot_date",
                target_pool=vault_pool,
                target_table="pit_customer",
                hub_hash_key_column="hub_hk",
                snapshot_date_column="snapshot_date",
                satellite_configs=_SAT_CFG,
                _config=KnotConfig(id="pit_ptr"),
            )
        assert (await t.run(RunRequest())).succeeded
        rows = await vault_pool.fetch_all(
            "SELECT hub_hk, snapshot_date, sat_customer_load_date "
            "FROM pit_customer ORDER BY hub_hk, snapshot_date"
        )
        by_key = {(r[0], r[1]): r[2] for r in rows}
        assert by_key[("hk_1", "2026-01-01")] == "2025-12-01"
        assert by_key[("hk_1", "2026-02-01")] == "2026-01-15"

    async def test_rebuild_truncates_existing_rows(
        self, vault_pool: SqlitePool
    ) -> None:
        for run_id in ("pit_r1", "pit_r2"):
            with Tapestry() as t:
                DataVaultPITTableBuilder(
                    source_pool=vault_pool,
                    pit_spine_query="SELECT hub_hk, snapshot_date FROM pit_spine ORDER BY hub_hk, snapshot_date",
                    target_pool=vault_pool,
                    target_table="pit_customer",
                    hub_hash_key_column="hub_hk",
                    snapshot_date_column="snapshot_date",
                    satellite_configs=_SAT_CFG,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await vault_pool.fetch_all("SELECT hub_hk FROM pit_customer")
        assert len(rows) == 3
