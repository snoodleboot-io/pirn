"""Tests for _LazyClient."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.backends.valkey._lazy_client import _LazyClient


class TestLazyClientConstruction(unittest.TestCase):
    """Construction validation."""

    def test_requires_client_or_config(self) -> None:
        with self.assertRaises(TypeError):
            _LazyClient()

    def test_accepts_injected_client(self) -> None:
        client = AsyncMock()
        lc = _LazyClient(client=client)
        self.assertIsNotNone(lc)

    def test_accepts_config(self) -> None:
        config = MagicMock()
        lc = _LazyClient(config=config)
        self.assertIsNotNone(lc)


class TestLazyClientGet(unittest.IsolatedAsyncioTestCase):
    """get() returns injected client immediately; lazy-builds from config."""

    async def test_get_returns_injected_client(self) -> None:
        client = AsyncMock()
        lc = _LazyClient(client=client)
        result = await lc.get()
        self.assertIs(result, client)

    async def test_get_lazy_builds_client_from_config(self) -> None:
        config = MagicMock()
        mock_client = AsyncMock()

        mock_glide_client_cls = MagicMock()
        mock_glide_client_cls.create = AsyncMock(return_value=mock_client)

        with patch.dict(
            "sys.modules",
            {"glide": MagicMock(GlideClient=mock_glide_client_cls)},
        ):
            lc = _LazyClient(config=config)
            result = await lc.get()

        self.assertIs(result, mock_client)

    async def test_get_raises_import_error_when_glide_missing(self) -> None:
        config = MagicMock()
        lc = _LazyClient(config=config)
        with patch.dict("sys.modules", {"glide": None}):
            with self.assertRaises(ImportError) as ctx:
                await lc.get()
        self.assertIn("valkey-glide", str(ctx.exception))


class TestLazyClientClose(unittest.IsolatedAsyncioTestCase):
    """close() only closes when client was lazy-built from config."""

    async def test_close_with_injected_client_does_not_close(self) -> None:
        client = AsyncMock()
        lc = _LazyClient(client=client)
        await lc.close()
        client.close.assert_not_called()

    async def test_close_with_config_closes_client(self) -> None:
        config = MagicMock()
        mock_client = AsyncMock()
        mock_glide_client_cls = MagicMock()
        mock_glide_client_cls.create = AsyncMock(return_value=mock_client)

        with patch.dict(
            "sys.modules",
            {"glide": MagicMock(GlideClient=mock_glide_client_cls)},
        ):
            lc = _LazyClient(config=config)
            await lc.get()  # triggers lazy build
            await lc.close()

        mock_client.close.assert_called_once()

    async def test_close_before_get_is_safe(self) -> None:
        config = MagicMock()
        lc = _LazyClient(config=config)
        # No exception even though no client was built
        await lc.close()
