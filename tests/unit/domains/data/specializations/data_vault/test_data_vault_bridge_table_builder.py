"""Tests for :class:`DataVaultBridgeTableBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_bridge_table_builder import (
    DataVaultBridgeTableBuilder,
)
from pirn.tapestry import Tapestry

_HUB_CONFIGS = [
    {
        "hub_table": "hub_customer",
        "hub_hash_key_column": "hub_hk",
        "link_fk_column": "customer_hk",
        "bridge_columns": ["customer_id"],
    },
    {
        "hub_table": "hub_product",
        "hub_hash_key_column": "hub_hk",
        "link_fk_column": "product_hk",
        "bridge_columns": ["product_code"],
    },
]
_TARGET_TABLE = "bridge_order"
_LINK_TABLE = "link_order"
_LINK_HK_COL = "link_hk"


async def _make_vault_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE hub_customer ("
        "  hub_hk TEXT PRIMARY KEY,"
        "  customer_id INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO hub_customer (hub_hk, customer_id) VALUES (?, ?)",
        [("chk_1", 101), ("chk_2", 102)],
    )
    await pool.execute(
        "CREATE TABLE hub_product ("
        "  hub_hk TEXT PRIMARY KEY,"
        "  product_code TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO hub_product (hub_hk, product_code) VALUES (?, ?)",
        [("phk_a", "SKU-A"), ("phk_b", "SKU-B")],
    )
    await pool.execute(
        "CREATE TABLE link_order ("
        "  link_hk TEXT PRIMARY KEY,"
        "  customer_hk TEXT NOT NULL,"
        "  product_hk TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO link_order (link_hk, customer_hk, product_hk) VALUES (?, ?, ?)",
        [("lhk_1", "chk_1", "phk_a"), ("lhk_2", "chk_2", "phk_b")],
    )
    await pool.execute(
        "CREATE TABLE bridge_order ("
        "  link_hk TEXT NOT NULL,"
        "  customer_id INTEGER,"
        "  product_code TEXT"
        ")"
    )
    return pool


def _make_knot(pool: SqlitePool) -> DataVaultBridgeTableBuilder:
    return DataVaultBridgeTableBuilder(
        source_pool=pool,
        target_pool=pool,
        target_table=_TARGET_TABLE,
        link_table=_LINK_TABLE,
        link_hash_key_column=_LINK_HK_COL,
        hub_configs=_HUB_CONFIGS,
        _config=KnotConfig(id="bridge"),
    )


class TestDataVaultBridgeTableBuilder(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_builds_flat_rows_from_link_and_hubs(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT link_hk, customer_id, product_code FROM bridge_order ORDER BY link_hk"
        )
        assert rows == [("lhk_1", 101, "SKU-A"), ("lhk_2", 102, "SKU-B")]

    async def test_rebuild_truncates_existing_rows(self) -> None:
        for run_id in ("bridge_r1", "bridge_r2"):
            with Tapestry() as t:
                DataVaultBridgeTableBuilder(
                    source_pool=self.pool,
                    target_pool=self.pool,
                    target_table=_TARGET_TABLE,
                    link_table=_LINK_TABLE,
                    link_hash_key_column=_LINK_HK_COL,
                    hub_configs=_HUB_CONFIGS,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.pool.fetch_all("SELECT link_hk FROM bridge_order")
        assert len(rows) == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_link_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_link_table() -> str:
            return _LINK_TABLE

        with Tapestry() as t:
            lt_knot = emit_link_table(_config=KnotConfig(id="lt"))
            DataVaultBridgeTableBuilder(
                source_pool=self.pool,
                target_pool=self.pool,
                target_table=_TARGET_TABLE,
                link_table=lt_knot,
                link_hash_key_column=_LINK_HK_COL,
                hub_configs=_HUB_CONFIGS,
                _config=KnotConfig(id="bridge"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["bridge"]["rows_written"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_vault_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> DataVaultBridgeTableBuilder:
        defaults: dict[str, Any] = {
            "source_pool": self.pool,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
            "link_table": _LINK_TABLE,
            "link_hash_key_column": _LINK_HK_COL,
            "hub_configs": _HUB_CONFIGS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DataVaultBridgeTableBuilder(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DataVaultBridgeTableBuilder, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.pool,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
            "link_table": _LINK_TABLE,
            "link_hash_key_column": _LINK_HK_COL,
            "hub_configs": _HUB_CONFIGS,
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

    async def test_rejects_empty_hub_configs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "hub_configs"):
            await self._call(k, hub_configs=[])

    async def test_rejects_hub_config_missing_required_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "missing required key"):
            await self._call(k, hub_configs=[{"hub_table": "hub_customer"}])

    async def test_rejects_invalid_link_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, link_table="bad; DROP TABLE x")

    async def test_rejects_empty_link_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "link_table"):
            await self._call(k, link_table="")
