"""Tests for :class:`SchemaVersionMigrator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.schema_version_migrator import (
    SchemaVersionMigrator,
)
from pirn.tapestry import Tapestry

_MIGRATIONS = [
    (1, "CREATE TABLE users (id INTEGER)"),
    (2, "CREATE TABLE orders (id INTEGER)"),
]


async def _make_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute("CREATE TABLE schema_migrations (version INTEGER, applied_at TEXT)")
    return pool


def _make_knot(pool: SqlitePool, **overrides: Any) -> SchemaVersionMigrator:
    defaults: dict[str, Any] = {
        "pool": pool,
        "migrations": _MIGRATIONS,
        "_config": KnotConfig(id="mig"),
    }
    defaults.update(overrides)
    return SchemaVersionMigrator(**defaults)


class TestSchemaVersionMigrator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_applies_all_migrations_on_fresh_db(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["mig"]
        assert output["applied"] == [1, 2]
        assert output["skipped"] == []

    async def test_skips_already_applied(self) -> None:
        await self.pool.execute(
            "INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')"
        )
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["mig"]
        assert output["applied"] == [2]
        assert output["skipped"] == [1]

    async def test_fails_on_version_gap(self) -> None:
        await self.pool.execute(
            "INSERT INTO schema_migrations VALUES (1, '2026-01-01T00:00:00+00:00')"
        )
        with Tapestry() as t:
            _make_knot(
                self.pool,
                migrations=[
                    (1, "CREATE TABLE users (id INTEGER)"),
                    (3, "CREATE TABLE orders (id INTEGER)"),
                ],
                _config=KnotConfig(id="mig-gap"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_idempotent_on_re_run(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        await t.run(RunRequest())
        with Tapestry() as t2:
            _make_knot(self.pool, _config=KnotConfig(id="mig2"))
        result = await t2.run(RunRequest())
        assert result.outputs["mig2"]["applied"] == []
        assert result.outputs["mig2"]["skipped"] == [1, 2]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_migrations_from_upstream_knot(self) -> None:
        @knot
        async def emit_migrations() -> list:
            return [(1, "CREATE TABLE wired (id INTEGER)")]

        with Tapestry() as t:
            m_knot = emit_migrations(_config=KnotConfig(id="m"))
            SchemaVersionMigrator(
                pool=self.pool,
                migrations=m_knot,
                _config=KnotConfig(id="mig-wire"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mig-wire"]["applied"] == [1]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> SchemaVersionMigrator:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "migrations": _MIGRATIONS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return SchemaVersionMigrator(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: SchemaVersionMigrator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "migrations": _MIGRATIONS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_migrations(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "migrations"):
            await self._call(k, migrations=[])

    async def test_rejects_unordered_migrations(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "ordered"):
            await self._call(
                k,
                migrations=[
                    (2, "CREATE TABLE b (id INTEGER)"),
                    (1, "CREATE TABLE a (id INTEGER)"),
                ],
            )

    async def test_rejects_duplicate_versions(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "unique"):
            await self._call(
                k,
                migrations=[
                    (1, "CREATE TABLE a (id INTEGER)"),
                    (1, "CREATE TABLE b (id INTEGER)"),
                ],
            )
