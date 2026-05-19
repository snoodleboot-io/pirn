"""Tests for SmartTransport — size/type-based routing."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.transport.inline_transport import InlineTransport
from pirn.core.transport.smart_transport import SmartTransport
from pirn.core.transport.transport_handle import TransportHandle


def _handle(transport_id: str, key: str = "k") -> TransportHandle:
    return TransportHandle(transport_id=transport_id, key=key, type_name="builtins.int", size_bytes=4, checksum="abc")


class TestSmartTransportRouting(unittest.IsolatedAsyncioTestCase):
    def _make(self, threshold: int = 1024 * 1024) -> tuple[SmartTransport, MagicMock, MagicMock]:
        fast = MagicMock(spec=InlineTransport)
        fast.transport_id = "fast"
        fast.begin_run = AsyncMock()
        fast.end_run = AsyncMock()
        fast.write = AsyncMock(return_value=_handle("fast"))
        fast.read = AsyncMock(return_value=42)
        fast.exists = AsyncMock(return_value=True)

        bulk = MagicMock(spec=InlineTransport)
        bulk.transport_id = "bulk"
        bulk.begin_run = AsyncMock()
        bulk.end_run = AsyncMock()
        bulk.write = AsyncMock(return_value=_handle("bulk"))
        bulk.read = AsyncMock(return_value=99)
        bulk.exists = AsyncMock(return_value=True)

        smart = SmartTransport(fast=fast, bulk=bulk, threshold_bytes=threshold)
        return smart, fast, bulk

    async def test_transport_id_combines_both(self) -> None:
        smart, _, _ = self._make()
        assert "fast" in smart.transport_id
        assert "bulk" in smart.transport_id

    async def test_small_value_routes_to_fast(self) -> None:
        smart, fast, bulk = self._make(threshold=1_000_000)
        await smart.begin_run("r1")
        await smart.write("r1", "k1", 42)
        fast.write.assert_called_once()
        bulk.write.assert_not_called()

    async def test_large_value_routes_to_bulk(self) -> None:
        smart, fast, bulk = self._make(threshold=1)
        await smart.begin_run("r1")
        big = b"x" * 1000
        await smart.write("r1", "k1", big)
        bulk.write.assert_called_once()
        fast.write.assert_not_called()

    async def test_large_type_routes_to_bulk_regardless_of_size(self) -> None:
        fast = MagicMock(spec=InlineTransport)
        fast.transport_id = "fast"
        fast.begin_run = AsyncMock()
        fast.write = AsyncMock(return_value=_handle("fast"))

        bulk = MagicMock(spec=InlineTransport)
        bulk.transport_id = "bulk"
        bulk.begin_run = AsyncMock()
        bulk.write = AsyncMock(return_value=_handle("bulk"))

        smart = SmartTransport(
            fast=fast, bulk=bulk, threshold_bytes=1_000_000, large_types=(list,)
        )
        await smart.begin_run("r1")
        await smart.write("r1", "k1", [1, 2, 3])
        bulk.write.assert_called_once()
        fast.write.assert_not_called()

    async def test_read_routes_by_handle_transport_id_fast(self) -> None:
        smart, fast, bulk = self._make()
        await smart.read(_handle("fast"))
        fast.read.assert_called_once()
        bulk.read.assert_not_called()

    async def test_read_routes_by_handle_transport_id_bulk(self) -> None:
        smart, fast, bulk = self._make()
        bulk.read = AsyncMock(return_value=99)
        await smart.read(_handle("bulk"))
        bulk.read.assert_called_once()
        fast.read.assert_not_called()

    async def test_read_unknown_handle_raises(self) -> None:
        smart, _, _ = self._make()
        with self.assertRaises(ValueError):
            await smart.read(_handle("unknown"))

    async def test_begin_run_calls_both(self) -> None:
        smart, fast, bulk = self._make()
        await smart.begin_run("r1")
        fast.begin_run.assert_called_once_with("r1")
        bulk.begin_run.assert_called_once_with("r1")

    async def test_end_run_calls_both(self) -> None:
        smart, fast, bulk = self._make()
        await smart.begin_run("r1")
        await smart.end_run("r1", success=True)
        fast.end_run.assert_called_once_with("r1", success=True)
        bulk.end_run.assert_called_once_with("r1", success=True)

    async def test_exists_routes_by_handle(self) -> None:
        smart, fast, bulk = self._make()
        await smart.exists(_handle("fast"))
        fast.exists.assert_called_once()
        bulk.exists.assert_not_called()

    async def test_probe_size_fallback_on_unregistered_type(self) -> None:
        smart, fast, bulk = self._make(threshold=999_999_999)
        await smart.begin_run("r1")
        await smart.write("r1", "k1", object())
        fast.write.assert_called_once()
