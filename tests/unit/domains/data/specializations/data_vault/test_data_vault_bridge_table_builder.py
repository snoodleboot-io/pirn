"""Tests for :class:`DataVaultBridgeTableBuilder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_bridge_table_builder import (
    DataVaultBridgeTableBuilder,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def vault_pool() -> SqlitePool:
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
    yield pool
    await pool.close()


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


class TestConstruction:
    def test_rejects_non_pool_source(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            with Tapestry():
                DataVaultBridgeTableBuilder(
                    source_pool="bad",  # type: ignore[arg-type]
                    target_pool=pool,
                    target_table="bridge_order",
                    link_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_configs=_HUB_CONFIGS,
                    _config=KnotConfig(id="bridge"),
                )

    def test_rejects_empty_hub_configs(self, vault_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="hub_configs"):
            with Tapestry():
                DataVaultBridgeTableBuilder(
                    source_pool=vault_pool,
                    target_pool=vault_pool,
                    target_table="bridge_order",
                    link_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_configs=[],
                    _config=KnotConfig(id="bridge"),
                )

    def test_rejects_hub_config_missing_required_key(
        self, vault_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="missing required key"):
            with Tapestry():
                DataVaultBridgeTableBuilder(
                    source_pool=vault_pool,
                    target_pool=vault_pool,
                    target_table="bridge_order",
                    link_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_configs=[{"hub_table": "hub_customer"}],
                    _config=KnotConfig(id="bridge"),
                )

    def test_rejects_invalid_link_table(self, vault_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            with Tapestry():
                DataVaultBridgeTableBuilder(
                    source_pool=vault_pool,
                    target_pool=vault_pool,
                    target_table="bridge_order",
                    link_table="bad; DROP TABLE x",
                    link_hash_key_column="link_hk",
                    hub_configs=_HUB_CONFIGS,
                    _config=KnotConfig(id="bridge"),
                )

    def test_rejects_empty_link_table(self, vault_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="link_table"):
            with Tapestry():
                DataVaultBridgeTableBuilder(
                    source_pool=vault_pool,
                    target_pool=vault_pool,
                    target_table="bridge_order",
                    link_table="",
                    link_hash_key_column="link_hk",
                    hub_configs=_HUB_CONFIGS,
                    _config=KnotConfig(id="bridge"),
                )


@pytest.mark.asyncio
class TestBridgeTableBuilderBehaviour:
    async def test_builds_flat_rows_from_link_and_hubs(
        self, vault_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DataVaultBridgeTableBuilder(
                source_pool=vault_pool,
                target_pool=vault_pool,
                target_table="bridge_order",
                link_table="link_order",
                link_hash_key_column="link_hk",
                hub_configs=_HUB_CONFIGS,
                _config=KnotConfig(id="bridge_build"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await vault_pool.fetch_all(
            "SELECT link_hk, customer_id, product_code FROM bridge_order ORDER BY link_hk"
        )
        assert rows == [("lhk_1", 101, "SKU-A"), ("lhk_2", 102, "SKU-B")]

    async def test_rebuild_truncates_existing_rows(
        self, vault_pool: SqlitePool
    ) -> None:
        for run_id in ("bridge_r1", "bridge_r2"):
            with Tapestry() as t:
                DataVaultBridgeTableBuilder(
                    source_pool=vault_pool,
                    target_pool=vault_pool,
                    target_table="bridge_order",
                    link_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_configs=_HUB_CONFIGS,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await vault_pool.fetch_all("SELECT link_hk FROM bridge_order")
        assert len(rows) == 2
