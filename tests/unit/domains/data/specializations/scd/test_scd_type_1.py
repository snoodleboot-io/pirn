"""Tests for :class:`ScdType1`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_1 import ScdType1
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name, region) VALUES (?, ?, ?)",
            [(1, "Alice", "EU"), (2, "Bob", "US")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ScdType1(
                source_pool="not-a-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )

    def test_rejects_empty_source_query(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "source_query"):
            ScdType1(
                source_pool=source_pool,
                source_query="",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )

    def test_rejects_pk_outside_columns(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "primary_keys not in column_names"):
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("missing",),
                column_names=("id", "name"),
                _config=KnotConfig(id="scd1"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id FROM customers",
                target_pool=target_pool,
                target_table="customers; DROP TABLE x",
                primary_keys=("id",),
                column_names=("id",),
                _config=KnotConfig(id="scd1"),
            )


class TestScdType1Behaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name, region) VALUES (?, ?, ?)",
            [(1, "Alice", "EU"), (2, "Bob", "US")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
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
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region FROM customers ORDER BY id"
        )
        assert rows == [(1, "Alice", "EU"), (2, "Bob", "US")]

    async def test_second_run_overwrites_changed_row(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        # First run.
        with Tapestry() as t:
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        assert (await t.run(RunRequest())).succeeded
        # Mutate one source row in place.
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        # Second run.
        with Tapestry() as t2:
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region FROM customers ORDER BY id"
        )
        # Type 1: history is lost — id=1's region overwrites in place.
        assert rows == [(1, "Alice", "APAC"), (2, "Bob", "US")]
