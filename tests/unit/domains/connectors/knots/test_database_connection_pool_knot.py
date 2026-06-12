"""Tests for :class:`DatabaseConnectionPoolKnot` calling process() directly."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.connectors.knots.database_connection_pool_knot import DatabaseConnectionPoolKnot


class TestDatabaseConnectionPoolKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_pool_unchanged(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        try:
            knot = DatabaseConnectionPoolKnot(pool=pool, _config=KnotConfig(id="pool"))
            result = await knot.process(pool=pool)
            assert result is pool
        finally:
            await pool.close()

    async def test_accepts_scalar_pool_at_build_time(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        try:
            # Scalar pool (not a Knot) is valid as a build-time config value
            knot = DatabaseConnectionPoolKnot(pool=pool, _config=KnotConfig(id="pool"))
            result = await knot.process(pool=pool)
            assert isinstance(result, SqlitePool)
        finally:
            await pool.close()
