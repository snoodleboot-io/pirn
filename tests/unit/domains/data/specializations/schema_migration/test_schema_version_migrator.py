"""Tests for :class:`SchemaVersionMigrator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.schema_version_migrator import (
    SchemaVersionMigrator,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE schema_migrations (version INTEGER, applied_at TEXT)"
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            SchemaVersionMigrator(
                pool="bad",  # type: ignore[arg-type]
                migrations=[(1, "CREATE TABLE t (id INTEGER)")],
                _config=KnotConfig(id="mig"),
            )

    def test_rejects_empty_migrations(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "migrations"):
            SchemaVersionMigrator(
                pool=pool,
                migrations=[],
                _config=KnotConfig(id="mig"),
            )

    def test_rejects_unordered_migrations(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "ordered"):
            SchemaVersionMigrator(
                pool=pool,
                migrations=[
                    (2, "CREATE TABLE b (id INTEGER)"),
                    (1, "CREATE TABLE a (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig"),
            )

    def test_rejects_duplicate_versions(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "unique"):
            SchemaVersionMigrator(
                pool=pool,
                migrations=[
                    (1, "CREATE TABLE a (id INTEGER)"),
                    (1, "CREATE TABLE b (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig"),
            )


class TestBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE schema_migrations (version INTEGER, applied_at TEXT)"
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_applies_all_migrations_on_fresh_db(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            SchemaVersionMigrator(
                pool=pool,
                migrations=[
                    (1, "CREATE TABLE users (id INTEGER)"),
                    (2, "CREATE TABLE orders (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["mig"]
        assert output["applied"] == [1, 2]
        assert output["skipped"] == []

    async def test_skips_already_applied(self) -> None:
        pool = self.pool
        await pool.execute(
            "INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')"
        )
        with Tapestry() as t:
            SchemaVersionMigrator(
                pool=pool,
                migrations=[
                    (1, "CREATE TABLE users (id INTEGER)"),
                    (2, "CREATE TABLE orders (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["mig"]
        assert output["applied"] == [2]
        assert output["skipped"] == [1]

    async def test_fails_on_version_gap(self) -> None:
        pool = self.pool
        await pool.execute(
            "INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')"
        )
        with Tapestry() as t:
            SchemaVersionMigrator(
                pool=pool,
                migrations=[
                    (1, "CREATE TABLE users (id INTEGER)"),
                    (3, "CREATE TABLE orders (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig-gap"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
