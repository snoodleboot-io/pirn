"""Tests for :class:`DataVaultHubLoader`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_hub_loader import (
    DataVaultHubLoader,
)
from pirn.tapestry import Tapestry


def _make_loader(
    source_pool: SqlitePool,
    target_pool: SqlitePool,
    *,
    knot_id: str = "hub",
) -> DataVaultHubLoader:
    with Tapestry():
        return DataVaultHubLoader(
            source_pool=source_pool,
            source_query="SELECT hk, customer_id FROM raw_customer",
            target_pool=target_pool,
            target_table="hub_customer",
            hash_key_column="hub_hk",
            business_key_columns=("customer_id",),
            record_source="test_system",
            _config=KnotConfig(id=knot_id),
        )


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE raw_customer ("
            "  hk TEXT NOT NULL,"
            "  customer_id INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO raw_customer (hk, customer_id) VALUES (?, ?)",
            [("hk_1", 1), ("hk_2", 2)],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE hub_customer ("
            "  hub_hk TEXT PRIMARY KEY,"
            "  customer_id INTEGER NOT NULL,"
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
                DataVaultHubLoader(
                    source_pool="bad",  # type: ignore[arg-type]
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="src",
                    _config=KnotConfig(id="hub"),
                )

    def test_rejects_non_pool_target(self) -> None:
        source_pool = self.source_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            with Tapestry():
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool="bad",  # type: ignore[arg-type]
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="src",
                    _config=KnotConfig(id="hub"),
                )

    def test_rejects_empty_source_query(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "source_query"):
            with Tapestry():
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="",
                    target_pool=target_pool,
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="src",
                    _config=KnotConfig(id="hub"),
                )

    def test_rejects_empty_record_source(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "record_source"):
            with Tapestry():
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="",
                    _config=KnotConfig(id="hub"),
                )

    def test_rejects_invalid_target_table(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            with Tapestry():
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="bad; DROP TABLE x",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="src",
                    _config=KnotConfig(id="hub"),
                )

    def test_rejects_business_key_clashing_with_envelope(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "clash"):
            with Tapestry():
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("load_date",),
                    record_source="src",
                    _config=KnotConfig(id="hub"),
                )


class TestHubLoaderBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE raw_customer ("
            "  hk TEXT NOT NULL,"
            "  customer_id INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO raw_customer (hk, customer_id) VALUES (?, ?)",
            [("hk_1", 1), ("hk_2", 2)],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE hub_customer ("
            "  hub_hk TEXT PRIMARY KEY,"
            "  customer_id INTEGER NOT NULL,"
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
            DataVaultHubLoader(
                source_pool=source_pool,
                source_query="SELECT hk, customer_id FROM raw_customer",
                target_pool=target_pool,
                target_table="hub_customer",
                hash_key_column="hub_hk",
                business_key_columns=("customer_id",),
                record_source="test_system",
                _config=KnotConfig(id="hub"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT hub_hk, customer_id FROM hub_customer ORDER BY customer_id"
        )
        assert rows == [("hk_1", 1), ("hk_2", 2)]

    async def test_second_run_is_noop_for_existing_keys(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        for run_id in ("hub_run1", "hub_run2"):
            with Tapestry() as t:
                DataVaultHubLoader(
                    source_pool=source_pool,
                    source_query="SELECT hk, customer_id FROM raw_customer",
                    target_pool=target_pool,
                    target_table="hub_customer",
                    hash_key_column="hub_hk",
                    business_key_columns=("customer_id",),
                    record_source="test_system",
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all("SELECT hub_hk FROM hub_customer")
        assert len(rows) == 2

    async def test_new_key_inserted_incrementally(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            DataVaultHubLoader(
                source_pool=source_pool,
                source_query="SELECT hk, customer_id FROM raw_customer WHERE customer_id = 1",
                target_pool=target_pool,
                target_table="hub_customer",
                hash_key_column="hub_hk",
                business_key_columns=("customer_id",),
                record_source="test_system",
                _config=KnotConfig(id="hub_partial"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            DataVaultHubLoader(
                source_pool=source_pool,
                source_query="SELECT hk, customer_id FROM raw_customer",
                target_pool=target_pool,
                target_table="hub_customer",
                hash_key_column="hub_hk",
                business_key_columns=("customer_id",),
                record_source="test_system",
                _config=KnotConfig(id="hub_full"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all("SELECT hub_hk FROM hub_customer ORDER BY customer_id")
        assert len(rows) == 2

    async def test_load_date_and_record_source_populated(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            DataVaultHubLoader(
                source_pool=source_pool,
                source_query="SELECT hk, customer_id FROM raw_customer WHERE customer_id = 1",
                target_pool=target_pool,
                target_table="hub_customer",
                hash_key_column="hub_hk",
                business_key_columns=("customer_id",),
                record_source="crm_system",
                _config=KnotConfig(id="hub_src"),
            )
        assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT record_source, load_date FROM hub_customer"
        )
        assert rows[0][0] == "crm_system"
        assert rows[0][1] is not None
