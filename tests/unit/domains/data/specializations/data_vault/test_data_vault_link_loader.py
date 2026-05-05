"""Tests for :class:`DataVaultLinkLoader`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_link_loader import (
    DataVaultLinkLoader,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE raw_order ("
            "  link_hk TEXT NOT NULL,"
            "  customer_hk TEXT NOT NULL,"
            "  product_hk TEXT NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO raw_order (link_hk, customer_hk, product_hk) VALUES (?, ?, ?)",
            [("lhk_1", "chk_1", "phk_a"), ("lhk_2", "chk_2", "phk_b")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE link_order ("
            "  link_hk TEXT PRIMARY KEY,"
            "  customer_hk TEXT NOT NULL,"
            "  product_hk TEXT NOT NULL,"
            "  load_date TEXT NOT NULL,"
            "  record_source TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            with Tapestry():
                DataVaultLinkLoader(
                    source_pool="bad",  # type: ignore[arg-type]
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_hash_key_columns=("customer_hk", "product_hk"),
                    record_source="src",
                    _config=KnotConfig(id="link"),
                )

    def test_rejects_empty_source_query(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "source_query"):
            with Tapestry():
                DataVaultLinkLoader(
                    source_pool=source_pool,
                    source_query="",
                    target_pool=target_pool,
                    target_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_hash_key_columns=("customer_hk", "product_hk"),
                    record_source="src",
                    _config=KnotConfig(id="link"),
                )

    def test_rejects_invalid_target_table(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            with Tapestry():
                DataVaultLinkLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="bad; DROP TABLE x",
                    link_hash_key_column="link_hk",
                    hub_hash_key_columns=("customer_hk", "product_hk"),
                    record_source="src",
                    _config=KnotConfig(id="link"),
                )

    def test_rejects_hub_key_clashing_with_link_key(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "clash"):
            with Tapestry():
                DataVaultLinkLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_hash_key_columns=("link_hk",),
                    record_source="src",
                    _config=KnotConfig(id="link"),
                )


class TestLinkLoaderBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE raw_order ("
            "  link_hk TEXT NOT NULL,"
            "  customer_hk TEXT NOT NULL,"
            "  product_hk TEXT NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO raw_order (link_hk, customer_hk, product_hk) VALUES (?, ?, ?)",
            [("lhk_1", "chk_1", "phk_a"), ("lhk_2", "chk_2", "phk_b")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE link_order ("
            "  link_hk TEXT PRIMARY KEY,"
            "  customer_hk TEXT NOT NULL,"
            "  product_hk TEXT NOT NULL,"
            "  load_date TEXT NOT NULL,"
            "  record_source TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_first_run_inserts_all_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            DataVaultLinkLoader(
                source_pool=source_pool,
                source_query="SELECT link_hk, customer_hk, product_hk FROM raw_order",
                target_pool=target_pool,
                target_table="link_order",
                link_hash_key_column="link_hk",
                hub_hash_key_columns=("customer_hk", "product_hk"),
                record_source="order_system",
                _config=KnotConfig(id="link"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT link_hk FROM link_order ORDER BY link_hk"
        )
        assert rows == [("lhk_1",), ("lhk_2",)]

    async def test_second_run_is_noop_for_existing_links(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        for run_id in ("link_r1", "link_r2"):
            with Tapestry() as t:
                DataVaultLinkLoader(
                    source_pool=source_pool,
                    source_query="SELECT link_hk, customer_hk, product_hk FROM raw_order",
                    target_pool=target_pool,
                    target_table="link_order",
                    link_hash_key_column="link_hk",
                    hub_hash_key_columns=("customer_hk", "product_hk"),
                    record_source="order_system",
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all("SELECT link_hk FROM link_order")
        assert len(rows) == 2

    async def test_load_date_and_record_source_populated(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            DataVaultLinkLoader(
                source_pool=source_pool,
                source_query="SELECT link_hk, customer_hk, product_hk FROM raw_order WHERE link_hk = 'lhk_1'",
                target_pool=target_pool,
                target_table="link_order",
                link_hash_key_column="link_hk",
                hub_hash_key_columns=("customer_hk", "product_hk"),
                record_source="order_system",
                _config=KnotConfig(id="link_src"),
            )
        assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT record_source, load_date FROM link_order"
        )
        assert rows[0][0] == "order_system"
        assert rows[0][1] is not None
