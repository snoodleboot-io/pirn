"""Tests for :class:`DatabaseConnectionPool`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class TestDatabaseConnectionPoolInterface(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().acquire()

    async def test_release_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().release(None)

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().close()


class TestDatabaseConnectionPoolHelpers(unittest.TestCase):
    def test_reject_inline_interpolation_braces(self) -> None:
        pool = DatabaseConnectionPool()
        with self.assertRaises(ValueError):
            pool._reject_inline_interpolation("SELECT {col} FROM t")

    def test_reject_inline_interpolation_printf(self) -> None:
        pool = DatabaseConnectionPool()
        with self.assertRaises(ValueError):
            pool._reject_inline_interpolation("SELECT %s FROM t")

    def test_valid_query_passes(self) -> None:
        pool = DatabaseConnectionPool()
        pool._reject_inline_interpolation("SELECT id FROM t WHERE id = ?")

    def test_clear_credentials_nulls_config(self) -> None:
        pool = DatabaseConnectionPool()
        pool._config = "secret"  # type: ignore[attr-defined]
        pool._clear_credentials()
        self.assertIsNone(pool._config)  # type: ignore[attr-defined]
