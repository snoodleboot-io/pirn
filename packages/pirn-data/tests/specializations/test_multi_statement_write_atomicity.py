"""The multi-statement history writes are atomic (PIR-873).

``ScdType2``, ``ScdType7``, ``DataVaultSatelliteLoader`` and ``DeleteSafeSync`` each
write history by issuing two or three statements that only make sense together:
expire-then-insert, close-then-insert, upsert-then-soft-delete. Before PIR-873 they
issued them straight at the pool, one statement at a time, so a failure between
them left the table half-written — keys expired with no replacement version, a
satellite row closed with nothing open, a sync with some keys updated and the rest
carrying the previous run's state.

Each test here wedges a real failure between the statements — a ``CHECK`` constraint
the second statement violates, on a real SQLite target, so the raise is the engine's
``sqlite3.IntegrityError`` and not a stand-in's — and asserts the first statement's
effect is **gone**. That assertion fails on the pre-PIR-873 tree, where the first
statement had already been committed by the pool.
"""

from __future__ import annotations

import sqlite3
import unittest

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig

from pirn_data.specializations.data_vault.data_vault_satellite_loader import (
    DataVaultSatelliteLoader,
)
from pirn_data.specializations.incremental.delete_safe_sync import DeleteSafeSync
from pirn_data.specializations.scd.scd_type_2 import ScdType2
from pirn_data.specializations.scd.scd_type_7 import ScdType7


class TestScdType2Atomicity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        # The CHECK makes the *insert* fail while the expire has already run.
        await self.pool.execute(
            "CREATE TABLE dim ("
            "  id INTEGER NOT NULL, name TEXT NOT NULL CHECK (name <> 'BAD'),"
            "  valid_from TEXT NOT NULL, valid_to TEXT, is_current INTEGER NOT NULL)"
        )
        await self.pool.execute(
            "INSERT INTO dim VALUES (1, 'ok', '2020-01-01T00:00:00+00:00', NULL, 1)"
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _knot(self, rows: list[tuple[object, ...]]) -> ScdType2:
        return ScdType2(
            rows=rows,
            target_pool=self.pool,
            target_table="dim",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd2"),
        )

    async def test_failed_insert_rolls_back_the_expire(self) -> None:
        rows = [(1, "BAD")]
        with self.assertRaises(sqlite3.IntegrityError):
            await self._knot(rows).process(
                rows=rows,
                target_pool=self.pool,
                target_table="dim",
                primary_keys=("id",),
                column_names=("id", "name"),
            )
        # The expire must not have survived: id 1 is still the current version.
        assert await self.pool.fetch_all("SELECT id, name, valid_to, is_current FROM dim") == [
            (1, "ok", None, 1)
        ]

    async def test_successful_run_still_commits(self) -> None:
        rows = [(1, "changed")]
        summary = await self._knot(rows).process(
            rows=rows,
            target_pool=self.pool,
            target_table="dim",
            primary_keys=("id",),
            column_names=("id", "name"),
        )
        assert summary["rows_expired"] == 1
        assert summary["rows_inserted"] == 1
        assert await self.pool.fetch_all(
            "SELECT name, is_current FROM dim ORDER BY is_current"
        ) == [("ok", 0), ("changed", 1)]


class TestScdType7Atomicity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = SqlitePool(SqliteConfig(database=":memory:"))
        await self.pool.execute(
            "CREATE TABLE dim7 ("
            "  scd_id INTEGER NOT NULL, id INTEGER NOT NULL,"
            "  name TEXT NOT NULL CHECK (name <> 'BAD'),"
            "  valid_from TEXT NOT NULL, valid_to TEXT, is_current INTEGER NOT NULL)"
        )
        await self.pool.execute(
            "INSERT INTO dim7 VALUES (1, 1, 'ok', '2020-01-01T00:00:00+00:00', NULL, 1)"
        )

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_failed_insert_rolls_back_the_expire(self) -> None:
        rows = [(1, "BAD")]
        knot = ScdType7(
            rows=rows,
            target_pool=self.pool,
            target_table="dim7",
            primary_keys=("id",),
            column_names=("id", "name"),
            _config=KnotConfig(id="scd7"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            await knot.process(
                rows=rows,
                target_pool=self.pool,
                target_table="dim7",
                primary_keys=("id",),
                column_names=("id", "name"),
            )
        assert await self.pool.fetch_all("SELECT scd_id, valid_to, is_current FROM dim7") == [
            (1, None, 1)
        ]


class TestDataVaultSatelliteLoaderAtomicity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.source = SqlitePool(SqliteConfig(database=":memory:"))
        await self.source.execute(
            "CREATE TABLE stg (hk TEXT NOT NULL, hd TEXT NOT NULL, tier TEXT NOT NULL)"
        )
        self.target = SqlitePool(SqliteConfig(database=":memory:"))
        await self.target.execute(
            "CREATE TABLE sat ("
            "  hk TEXT NOT NULL, hd TEXT NOT NULL,"
            "  tier TEXT NOT NULL CHECK (tier <> 'BAD'),"
            "  load_date TEXT NOT NULL, load_end_date TEXT, record_source TEXT NOT NULL)"
        )
        await self.target.execute(
            "INSERT INTO sat VALUES ('h1', 'd1', 'gold', '2020-01-01', NULL, 'stg')"
        )

    async def asyncTearDown(self) -> None:
        await self.source.close()
        await self.target.close()

    async def _run(self) -> dict[str, object]:
        knot = DataVaultSatelliteLoader(
            source_pool=self.source,
            source_query="SELECT hk, hd, tier FROM stg",
            target_pool=self.target,
            target_table="sat",
            hub_hash_key_column="hk",
            attribute_columns=("tier",),
            hash_diff_column="hd",
            load_date_column="load_date",
            load_end_date_column="load_end_date",
            record_source_column="record_source",
            record_source="stg",
            _config=KnotConfig(id="sat"),
        )
        return await knot.process(
            source_pool=self.source,
            source_query="SELECT hk, hd, tier FROM stg",
            target_pool=self.target,
            target_table="sat",
            hub_hash_key_column="hk",
            attribute_columns=("tier",),
            hash_diff_column="hd",
            load_date_column="load_date",
            load_end_date_column="load_end_date",
            record_source_column="record_source",
            record_source="stg",
        )

    async def test_failed_insert_rolls_back_the_close(self) -> None:
        await self.source.execute("INSERT INTO stg VALUES ('h1', 'd2', 'BAD')")
        with self.assertRaises(sqlite3.IntegrityError):
            await self._run()
        # The close must not have survived: h1's satellite row is still open.
        assert await self.target.fetch_all("SELECT hd, load_end_date FROM sat") == [("d1", None)]

    async def test_successful_run_closes_and_inserts(self) -> None:
        await self.source.execute("INSERT INTO stg VALUES ('h1', 'd2', 'platinum')")
        summary = await self._run()
        assert summary["rows_closed"] == 1
        assert summary["rows_inserted"] == 1
        rows = await self.target.fetch_all("SELECT hd, tier FROM sat ORDER BY hd")
        assert rows == [("d1", "gold"), ("d2", "platinum")]

    async def test_unchanged_hash_diff_writes_nothing(self) -> None:
        await self.source.execute("INSERT INTO stg VALUES ('h1', 'd1', 'gold')")
        summary = await self._run()
        assert summary["rows_closed"] == 0
        assert summary["rows_inserted"] == 0


class TestDeleteSafeSyncReviveAndAtomicity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.source = SqlitePool(SqliteConfig(database=":memory:"))
        await self.source.execute(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        self.target = SqlitePool(SqliteConfig(database=":memory:"))
        await self.target.execute(
            "CREATE TABLE accounts ("
            "  id INTEGER PRIMARY KEY, name TEXT NOT NULL CHECK (name <> 'BAD'),"
            "  is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT)"
        )

    async def asyncTearDown(self) -> None:
        await self.source.close()
        await self.target.close()

    async def _sync(self) -> dict[str, object]:
        knot = DeleteSafeSync(
            source_pool=self.source,
            source_query="SELECT id, name FROM accounts ORDER BY id",
            target_pool=self.target,
            target_table="accounts",
            key_columns=("id",),
            non_key_columns=("name",),
            _config=KnotConfig(id="sync"),
        )
        return await knot.process(
            source_pool=self.source,
            source_query="SELECT id, name FROM accounts ORDER BY id",
            target_pool=self.target,
            target_table="accounts",
            key_columns=("id",),
            non_key_columns=("name",),
        )

    async def test_a_reappearing_key_is_revived(self) -> None:
        """The defect: an update left ``is_deleted = 1``, so the row stayed invisible."""
        await self.source.execute_many(
            "INSERT INTO accounts (id, name) VALUES (?, ?)", [(1, "Alice"), (2, "Bob")]
        )
        await self._sync()
        await self.source.execute("DELETE FROM accounts WHERE id = 2")
        assert (await self._sync())["rows_soft_deleted"] == 1
        assert await self.target.fetch_all("SELECT is_deleted FROM accounts WHERE id = 2") == [(1,)]

        await self.source.execute("INSERT INTO accounts (id, name) VALUES (2, 'Bob again')")
        summary = await self._sync()
        assert summary["rows_updated"] == 2
        assert await self.target.fetch_all(
            "SELECT name, is_deleted, deleted_at FROM accounts WHERE id = 2"
        ) == [("Bob again", 0, None)]

    async def test_an_already_deleted_key_keeps_its_deleted_at(self) -> None:
        """Re-stamping ``deleted_at`` every run lost the instant the row disappeared."""
        await self.source.execute("INSERT INTO accounts (id, name) VALUES (1, 'Alice')")
        await self._sync()
        await self.source.execute("DELETE FROM accounts WHERE id = 1")
        await self.source.execute("INSERT INTO accounts (id, name) VALUES (2, 'Bob')")
        await self._sync()
        first = await self.target.fetch_all("SELECT deleted_at FROM accounts WHERE id = 1")
        summary = await self._sync()
        assert summary["rows_soft_deleted"] == 0
        assert await self.target.fetch_all("SELECT deleted_at FROM accounts WHERE id = 1") == first

    async def test_failed_update_rolls_back_the_soft_deletes(self) -> None:
        await self.source.execute_many(
            "INSERT INTO accounts (id, name) VALUES (?, ?)", [(1, "Alice"), (2, "Bob")]
        )
        await self._sync()
        # id 2 disappears (a soft-delete) and id 1 changes to a value the CHECK
        # refuses (a failing update). Neither may survive.
        await self.source.execute("DELETE FROM accounts WHERE id = 2")
        await self.source.execute("UPDATE accounts SET name = 'BAD' WHERE id = 1")
        with self.assertRaises(sqlite3.IntegrityError):
            await self._sync()
        assert await self.target.fetch_all(
            "SELECT id, name, is_deleted FROM accounts ORDER BY id"
        ) == [(1, "Alice", 0), (2, "Bob", 0)]

    async def test_markers_may_not_be_sync_columns(self) -> None:
        knot = DeleteSafeSync(
            source_pool=self.source,
            source_query="SELECT id, name FROM accounts",
            target_pool=self.target,
            target_table="accounts",
            key_columns=("id",),
            non_key_columns=("name",),
            _config=KnotConfig(id="sync"),
        )
        with self.assertRaisesRegex(ValueError, "delete markers must not appear"):
            await knot.process(
                source_pool=self.source,
                source_query="SELECT id, name FROM accounts",
                target_pool=self.target,
                target_table="accounts",
                key_columns=("id",),
                non_key_columns=("name", "is_deleted"),
            )
