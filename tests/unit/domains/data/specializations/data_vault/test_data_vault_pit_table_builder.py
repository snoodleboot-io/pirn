"""Tests for :class:`DataVaultPITTableBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_pit_table_builder import (
    DataVaultPITTableBuilder,
)
from pirn.tapestry import Tapestry

_SAT_CFG = [
    {
        "table": "sat_customer",
        "hub_hash_key_column": "hub_hk",
        "load_date_column": "load_date",
        "load_end_date_column": "load_end_date",
        "pit_pointer_column": "sat_customer_load_date",
    }
]
_PIT_SPINE_QUERY = (
    "SELECT hub_hk, snapshot_date FROM pit_spine ORDER BY hub_hk, snapshot_date"
)
_TARGET_TABLE = "pit_customer"
_HUB_HK_COL = "hub_hk"
_SNAPSHOT_COL = "snapshot_date"


async def _make_vault_pool() -> SqlitePool:
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
        "INSERT INTO sat_customer"
        " (hub_hk, hash_diff, load_date, load_end_date) VALUES (?, ?, ?, ?)",
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
    return pool


def _make_knot(pool: SqlitePool) -> DataVaultPITTableBuilder:
    return DataVaultPITTableBuilder(
        source_pool=pool,
        pit_spine_query=_PIT_SPINE_QUERY,
        target_pool=pool,
        target_table=_TARGET_TABLE,
        hub_hash_key_column=_HUB_HK_COL,
        snapshot_date_column=_SNAPSHOT_COL,
        satellite_configs=_SAT_CFG,
        _config=KnotConfig(id="pit"),
    )


class TestDataVaultPITTableBuilder(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_builds_pit_rows_for_all_spine_entries(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT hub_hk, snapshot_date, sat_customer_load_date "
            "FROM pit_customer ORDER BY hub_hk, snapshot_date"
        )
        assert len(rows) == 3

    async def test_pointer_resolves_correct_as_of_version(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        assert (await t.run(RunRequest())).succeeded
        rows = await self.pool.fetch_all(
            "SELECT hub_hk, snapshot_date, sat_customer_load_date "
            "FROM pit_customer ORDER BY hub_hk, snapshot_date"
        )
        by_key = {(r[0], r[1]): r[2] for r in rows}
        assert by_key[("hk_1", "2026-01-01")] == "2025-12-01"
        assert by_key[("hk_1", "2026-02-01")] == "2026-01-15"

    async def test_rebuild_truncates_existing_rows(self) -> None:
        for run_id in ("pit_r1", "pit_r2"):
            with Tapestry() as t:
                DataVaultPITTableBuilder(
                    source_pool=self.pool,
                    pit_spine_query=_PIT_SPINE_QUERY,
                    target_pool=self.pool,
                    target_table=_TARGET_TABLE,
                    hub_hash_key_column=_HUB_HK_COL,
                    snapshot_date_column=_SNAPSHOT_COL,
                    satellite_configs=_SAT_CFG,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.pool.fetch_all("SELECT hub_hk FROM pit_customer")
        assert len(rows) == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_pit_spine_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _PIT_SPINE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            DataVaultPITTableBuilder(
                source_pool=self.pool,
                pit_spine_query=q_knot,
                target_pool=self.pool,
                target_table=_TARGET_TABLE,
                hub_hash_key_column=_HUB_HK_COL,
                snapshot_date_column=_SNAPSHOT_COL,
                satellite_configs=_SAT_CFG,
                _config=KnotConfig(id="pit"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["pit"]["rows_written"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> DataVaultPITTableBuilder:
        defaults: dict[str, Any] = {
            "source_pool": self.pool,
            "pit_spine_query": _PIT_SPINE_QUERY,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
            "hub_hash_key_column": _HUB_HK_COL,
            "snapshot_date_column": _SNAPSHOT_COL,
            "satellite_configs": _SAT_CFG,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DataVaultPITTableBuilder(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DataVaultPITTableBuilder, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.pool,
            "pit_spine_query": _PIT_SPINE_QUERY,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
            "hub_hash_key_column": _HUB_HK_COL,
            "snapshot_date_column": _SNAPSHOT_COL,
            "satellite_configs": _SAT_CFG,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_satellite_configs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "satellite_configs"):
            await self._call(k, satellite_configs=[])

    async def test_rejects_sat_config_missing_required_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "missing required key"):
            await self._call(k, satellite_configs=[{"table": "sat_customer"}])

    async def test_rejects_invalid_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad; DROP TABLE x")

    async def test_rejects_empty_pit_spine_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "pit_spine_query"):
            await self._call(k, pit_spine_query="")
