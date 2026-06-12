"""Tests for :class:`DatabaseConnectionPoolKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.knots.database_connection_pool_knot import (
    DatabaseConnectionPoolKnot,
)
from pirn.tapestry import Tapestry


class _FakePool(DatabaseConnectionPool):
    """Minimal concrete pool for testing."""

    async def acquire(self) -> None:  # type: ignore[override]
        return None

    async def release(self, connection: object) -> None:
        pass

    async def close(self) -> None:
        pass


class TestDatabaseConnectionPoolKnot(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_pool_unchanged(self) -> None:
        pool = _FakePool()
        with Tapestry():
            k = DatabaseConnectionPoolKnot(pool=pool, _config=KnotConfig(id="pool_knot"))
        result = await k.process(pool=pool)
        assert result is pool

    async def test_process_with_different_pool_instance(self) -> None:
        pool_a = _FakePool()
        pool_b = _FakePool()
        with Tapestry():
            k = DatabaseConnectionPoolKnot(pool=pool_a, _config=KnotConfig(id="pk2"))
        result = await k.process(pool=pool_b)
        assert result is pool_b
