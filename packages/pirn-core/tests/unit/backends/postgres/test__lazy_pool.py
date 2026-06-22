"""Tests for _LazyPool."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.backends.postgres._lazy_pool import _LazyPool


class TestLazyPoolConstruction(unittest.TestCase):
    def test_requires_pool_or_dsn(self) -> None:
        with self.assertRaises(TypeError):
            _LazyPool()

    def test_accepts_injected_pool(self) -> None:
        pool = MagicMock()
        lp = _LazyPool(pool=pool)
        self.assertIsNotNone(lp)

    def test_accepts_dsn_string(self) -> None:
        lp = _LazyPool(dsn="postgresql://user:pass@host/db")
        self.assertIsNotNone(lp)

    def test_dsn_display_redacts_credentials(self) -> None:
        lp = _LazyPool(dsn="postgresql://user:secret@host/db")
        self.assertNotIn("secret", lp._dsn_display)
        self.assertIn("<redacted>", lp._dsn_display)

    def test_dsn_display_none_for_injected_pool(self) -> None:
        pool = MagicMock()
        lp = _LazyPool(pool=pool)
        self.assertIsNone(lp._dsn_display)


class TestLazyPoolGet(unittest.IsolatedAsyncioTestCase):
    async def test_get_returns_injected_pool(self) -> None:
        pool = MagicMock()
        lp = _LazyPool(pool=pool)
        result = await lp.get()
        self.assertIs(result, pool)

    async def test_get_lazy_builds_pool_from_dsn(self) -> None:
        mock_pool = MagicMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            lp = _LazyPool(dsn="postgresql://user:pass@host/db")
            result = await lp.get()

        self.assertIs(result, mock_pool)

    async def test_get_raises_import_error_when_asyncpg_missing(self) -> None:
        from unittest.mock import patch
        lp = _LazyPool(dsn="postgresql://user:pass@host/db")
        with patch.dict("sys.modules", {"asyncpg": None}):
            with self.assertRaises(ImportError) as ctx:
                await lp.get()
        self.assertIn("asyncpg", str(ctx.exception))

    async def test_get_sanitizes_exception_message_on_connect_failure(self) -> None:
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(
            side_effect=Exception("could not connect to postgresql://user:secret@host/db")
        )

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            lp = _LazyPool(dsn="postgresql://user:secret@host/db")
            with self.assertRaises(Exception) as ctx:
                await lp.get()

        self.assertNotIn("secret", str(ctx.exception))


class TestLazyPoolClose(unittest.IsolatedAsyncioTestCase):
    async def test_close_injected_pool_does_not_close(self) -> None:
        pool = AsyncMock()
        lp = _LazyPool(pool=pool)
        await lp.close()
        pool.close.assert_not_called()

    async def test_close_lazy_pool_closes_it(self) -> None:
        mock_pool = AsyncMock()
        mock_asyncpg = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            lp = _LazyPool(dsn="postgresql://user:pass@host/db")
            await lp.get()
            await lp.close()

        mock_pool.close.assert_called_once()
