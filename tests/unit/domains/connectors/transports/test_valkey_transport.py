"""Unit tests for :class:`ValkeyTransport` — fully mocked, no live server required."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle
from pirn.connectors.transports.valkey_transport import ValkeyTransport


def _make_transport(**kwargs: object) -> ValkeyTransport:
    defaults = {"host": "localhost", "port": 6379}
    defaults.update(kwargs)  # type: ignore[arg-type]
    return ValkeyTransport(**defaults)  # type: ignore[arg-type]


def _mock_client() -> AsyncMock:
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.exists = AsyncMock(return_value=1)
    client.delete = AsyncMock(return_value=1)
    return client


class TestValkeyTransportInit(unittest.TestCase):
    def test_invalid_mode_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            _make_transport(mode="bad_mode")

    def test_write_over_without_slot_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            _make_transport(mode="write_over", slot_name="")

    def test_write_over_with_slot_name_ok(self) -> None:
        t = _make_transport(mode="write_over", slot_name="dashboard")
        assert "write_over" in t.transport_id

    def test_transport_id_contains_host_and_port(self) -> None:
        t = _make_transport(host="valkey.local", port=7379)
        assert "valkey.local" in t.transport_id
        assert "7379" in t.transport_id


class TestValkeyTransportWriteRead(unittest.IsolatedAsyncioTestCase):
    async def _transport_with_mock_client(self, **kwargs: object) -> ValkeyTransport:
        t = _make_transport(**kwargs)
        client = _mock_client()
        with patch.object(t, "_connect", return_value=client):
            await t.begin_run("run-1")
        t._client = client
        return t

    async def test_write_before_begin_run_raises(self) -> None:
        t = _make_transport()
        with self.assertRaises(TransportError):
            await t.write("run-1", "k", {"a": 1})

    async def test_read_before_begin_run_raises(self) -> None:
        t = _make_transport()
        handle = TransportHandle(
            transport_id="valkey:localhost:6379:content_addressed",
            key="pirn:run-1:k:abc",
            type_name="builtins.dict",
        )
        with self.assertRaises(TransportError):
            await t.read(handle)

    async def test_write_returns_handle(self) -> None:
        t = await self._transport_with_mock_client()
        handle = await t.write("run-1", "knot-a", {"score": 0.9})
        assert isinstance(handle, TransportHandle)
        assert handle.size_bytes > 0
        assert handle.checksum != ""

    async def test_write_calls_client_set(self) -> None:
        t = await self._transport_with_mock_client()
        await t.write("run-1", "k", {"x": 1})
        assert t._client.set.called

    async def test_read_returns_deserialised_value(self) -> None:
        from pirn.core.transport.serializers.pickle_serializer import PickleSerializer

        t = await self._transport_with_mock_client()
        value = {"answer": 42}
        raw = PickleSerializer().serialise(value)
        t._client.get = AsyncMock(return_value=raw)
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn:run-1:k:abc123",
            type_name="builtins.dict",
        )
        result = await t.read(handle)
        assert result == value

    async def test_read_missing_key_raises_transport_error(self) -> None:
        t = await self._transport_with_mock_client()
        t._client.get = AsyncMock(return_value=None)
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn:run-1:missing:abc",
            type_name="builtins.dict",
        )
        with self.assertRaises(TransportError):
            await t.read(handle)

    async def test_content_addressed_key_includes_run_id_and_knot_id(self) -> None:
        t = await self._transport_with_mock_client()
        handle = await t.write("run-xyz", "scorer", {"x": 1})
        assert "run-xyz" in handle.key
        assert "scorer" in handle.key

    async def test_write_over_key_uses_slot_name(self) -> None:
        t = await self._transport_with_mock_client(mode="write_over", slot_name="live")
        handle = await t.write("run-1", "k", {"x": 1})
        assert "live" in handle.key
        assert "latest" in handle.key

    async def test_exists_true_when_client_returns_nonzero(self) -> None:
        t = await self._transport_with_mock_client()
        t._client.exists = AsyncMock(return_value=1)
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn:run-1:k:abc",
            type_name="builtins.dict",
        )
        assert await t.exists(handle)

    async def test_exists_false_without_client(self) -> None:
        t = _make_transport()
        handle = TransportHandle(
            transport_id="valkey:localhost:6379:content_addressed",
            key="pirn:run-1:k:abc",
            type_name="builtins.dict",
        )
        assert not await t.exists(handle)


class TestValkeyTransportEndRun(unittest.IsolatedAsyncioTestCase):
    async def test_end_run_deletes_content_addressed_keys(self) -> None:
        t = _make_transport()
        client = _mock_client()
        with patch.object(t, "_connect", return_value=client):
            await t.begin_run("run-del")
        t._client = client
        await t.write("run-del", "k1", {"a": 1})
        await t.write("run-del", "k2", {"b": 2})
        await t.end_run("run-del", success=True)
        assert client.delete.called
        deleted_keys = client.delete.call_args[0][0]
        assert len(deleted_keys) == 2

    async def test_end_run_does_not_delete_write_over_keys(self) -> None:
        t = _make_transport(mode="write_over", slot_name="dash")
        client = _mock_client()
        with patch.object(t, "_connect", return_value=client):
            await t.begin_run("run-wo")
        t._client = client
        await t.write("run-wo", "k", {"a": 1})
        await t.end_run("run-wo", success=True)
        assert not client.delete.called


class TestValkeyTransportConnectionFailure(unittest.IsolatedAsyncioTestCase):
    async def test_connect_import_error_raises_import_error(self) -> None:
        t = _make_transport()
        with patch.object(t, "_connect", side_effect=ImportError("no glide")):
            with self.assertRaises(ImportError):
                await t.begin_run("run-fail")

    async def test_connect_runtime_error_raises_transport_error(self) -> None:
        t = _make_transport()
        with patch.object(t, "_connect", side_effect=TransportError("conn refused")):
            with self.assertRaises(TransportError):
                await t.begin_run("run-fail2")
