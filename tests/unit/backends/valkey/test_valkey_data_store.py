"""Tests for ValKeyDataStore (beyond signing which is covered in test_data_store_signing.py)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock

from pirn.backends._signer import _Signer
from pirn.backends.valkey.valkey_data_store import ValKeyDataStore


def _make_client_and_store(
    *,
    ttl_seconds: int | None = None,
    allow_unsigned: bool = True,
) -> tuple[AsyncMock, dict[str, bytes], "ValKeyDataStore"]:
    stored: dict[str, bytes] = {}

    async def fake_set(k: str, v: bytes, **kw: Any) -> None:
        stored[k] = v

    mock_client = AsyncMock()
    mock_client.set = fake_set
    mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))
    mock_client.exists = AsyncMock(side_effect=lambda keys: int(keys[0] in stored))
    mock_client.delete = AsyncMock(side_effect=lambda keys: stored.pop(keys[0], None))

    store = ValKeyDataStore(
        client=mock_client,
        ttl_seconds=ttl_seconds,
        allow_unsigned=allow_unsigned,
    )
    return mock_client, stored, store


class TestValKeyDataStoreConstruction(unittest.TestCase):
    def test_refuses_unsigned_without_opt_in(self) -> None:
        mock_client = AsyncMock()
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            ValKeyDataStore(client=mock_client)

    def test_allow_unsigned_permits_construction(self) -> None:
        mock_client = AsyncMock()
        store = ValKeyDataStore(client=mock_client, allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_requires_client_or_config(self) -> None:
        with self.assertRaises(TypeError):
            ValKeyDataStore(allow_unsigned=True)


class TestValKeyDataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    """put / get / has / scrub without signing."""

    def setUp(self) -> None:
        self.mock_client, self.stored, self.store = _make_client_and_store()

    async def test_put_then_get_returns_value(self) -> None:
        await self.store.put("sha256:abc", {"x": 1})
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, {"x": 1})

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_has_returns_false_before_put(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 99)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_value(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_key_prefix_applied(self) -> None:
        await self.store.put("sha256:abc", 42)
        keys = list(self.stored.keys())
        self.assertTrue(any("pirn:data:" in k for k in keys))


class TestValKeyDataStoreTTL(unittest.IsolatedAsyncioTestCase):
    """TTL path calls set with expiry."""

    async def test_put_with_ttl_invokes_expiry(self) -> None:
        import sys
        from unittest.mock import MagicMock, patch

        mock_expiry_set = MagicMock()
        mock_expiry_type = MagicMock()
        mock_expiry_type.SEC = "SEC"

        glide_mock = MagicMock(ExpirySet=mock_expiry_set, ExpiryType=mock_expiry_type)

        stored: dict[str, bytes] = {}
        set_calls: list[dict] = []

        async def fake_set(k: str, v: bytes, **kw: Any) -> None:
            stored[k] = v
            set_calls.append({"key": k, "kw": kw})

        mock_client = AsyncMock()
        mock_client.set = fake_set

        with patch.dict("sys.modules", {"glide": glide_mock}):
            store = ValKeyDataStore(
                client=mock_client,
                ttl_seconds=60,
                allow_unsigned=True,
            )
            await store.put("sha256:x", "val")

        self.assertEqual(len(set_calls), 1)
        # The expiry kwarg should have been passed
        self.assertIn("expiry", set_calls[0]["kw"])
