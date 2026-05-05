"""Tests for :class:`ScdType7`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_7 import ScdType7
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
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd7.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  scd_id INTEGER PRIMARY KEY,"
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
        self._tmp_target_pool.cleanup()
    def test_rejects_non_pool(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ScdType7(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd7"),
            )

    def test_rejects_invalid_surrogate_key_identifier(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ScdType7(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id",),
                surrogate_key_column="bad name",
                _config=KnotConfig(id="scd7"),
            )


class TestScdType7Behaviour(unittest.IsolatedAsyncioTestCase):

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
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd7.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  scd_id INTEGER PRIMARY KEY,"
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
        self._tmp_target_pool.cleanup()
    async def test_first_run_assigns_surrogate_keys(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType7(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd7"),
            )
        assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT scd_id, id, region, valid_to, is_current "
            "FROM customers ORDER BY scd_id"
        )
        assert len(rows) == 2
        # Surrogate ids are 1, 2.
        assert sorted(r[0] for r in rows) == [1, 2]
        for row in rows:
            assert row[3] is None
            assert row[4] == 1

    async def test_second_run_creates_new_version_with_new_surrogate(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType7(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd7"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            ScdType7(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd7"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT scd_id, id, region, is_current "
            "FROM customers ORDER BY scd_id"
        )
        # Three rows after the second run: original Alice, new Alice, Bob.
        assert len(rows) == 3
        # Old Alice is expired.
        alice_old = [r for r in rows if r[1] == 1 and r[3] == 0]
        assert len(alice_old) == 1
        assert alice_old[0][2] == "EU"
        # New Alice is current with a fresh surrogate id.
        alice_new = [r for r in rows if r[1] == 1 and r[3] == 1]
        assert len(alice_new) == 1
        assert alice_new[0][2] == "APAC"
        # Surrogate ids are unique and monotonic.
        scd_ids = [r[0] for r in rows]
        assert len(set(scd_ids)) == 3
        assert max(scd_ids) > 2
