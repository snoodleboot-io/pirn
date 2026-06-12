"""Unit tests for :class:`ObjectStoreTransport` — fully mocked ObjectStore."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

from pirn.core.transport.serializers.pickle_serializer import PickleSerializer
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle
from pirn.connectors.transports.object_store_transport import ObjectStoreTransport


def _make_store(*, chunks: list[bytes] | None = None, keys: list[str] | None = None) -> MagicMock:
    """Return a mock ObjectStore whose get/put/delete/list are pre-wired."""

    async def _get(key: str) -> AsyncIterator[bytes]:
        for chunk in chunks or []:
            yield chunk

    async def _list(prefix: str = "") -> AsyncIterator[str]:
        for k in keys or []:
            yield k

    store = MagicMock()
    store.get = AsyncMock(side_effect=_get)
    store.put = AsyncMock(return_value=None)
    store.delete = AsyncMock(return_value=None)
    store.list = AsyncMock(side_effect=_list)
    return store


def _transport(store: MagicMock, **kwargs: object) -> ObjectStoreTransport:
    return ObjectStoreTransport(store=store, **kwargs)  # type: ignore[arg-type]


class TestObjectStoreTransportInit(unittest.TestCase):
    def test_invalid_prefix_empty_raises(self) -> None:
        store = _make_store()
        with self.assertRaises(ValueError):
            ObjectStoreTransport(store=store, prefix="")

    def test_invalid_prefix_leading_slash_raises(self) -> None:
        store = _make_store()
        with self.assertRaises(ValueError):
            ObjectStoreTransport(store=store, prefix="/pirn")

    def test_invalid_prefix_trailing_slash_raises(self) -> None:
        store = _make_store()
        with self.assertRaises(ValueError):
            ObjectStoreTransport(store=store, prefix="pirn/")

    def test_transport_id_contains_store_class_name(self) -> None:
        store = _make_store()
        store.__class__.__name__ = "S3Store"
        t = _transport(store)
        assert "S3Store" in t.transport_id

    def test_transport_id_contains_prefix(self) -> None:
        store = _make_store()
        t = _transport(store, prefix="myapp")
        assert "myapp" in t.transport_id


class TestObjectStoreTransportWriteRead(unittest.IsolatedAsyncioTestCase):
    async def test_write_before_begin_run_raises(self) -> None:
        store = _make_store()
        t = _transport(store)
        with self.assertRaises(TransportError):
            await t.write("run-1", "k", {"a": 1})

    async def test_write_calls_store_put(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-1")
        await t.write("run-1", "scorer", {"x": 1})
        store.put.assert_called_once()
        key_arg = store.put.call_args[0][0]
        assert key_arg.startswith("pirn/run-1/scorer/")
        assert key_arg.endswith(".bin")

    async def test_write_returns_handle_with_key_and_checksum(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-2")
        handle = await t.write("run-2", "k", {"score": 0.9})
        assert isinstance(handle, TransportHandle)
        assert handle.key.startswith("pirn/run-2/")
        assert handle.checksum != ""
        assert handle.size_bytes > 0

    async def test_read_round_trips_value(self) -> None:
        value = {"patient": "anon", "result": [1, 2, 3]}
        raw = PickleSerializer().serialise(value)
        store = _make_store(chunks=[raw])
        t = _transport(store)
        await t.begin_run("run-3")
        handle = await t.write("run-3", "k", value)
        result = await t.read(handle)
        assert result == value

    async def test_read_store_error_raises_transport_error(self) -> None:
        store = _make_store()
        store.get = AsyncMock(side_effect=RuntimeError("network error"))
        t = _transport(store)
        await t.begin_run("run-4")
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn/run-4/k/abc.bin",
            type_name="builtins.dict",
        )
        with self.assertRaises(TransportError):
            await t.read(handle)

    async def test_prefix_appears_in_written_key(self) -> None:
        store = _make_store()
        t = _transport(store, prefix="myns")
        await t.begin_run("run-5")
        await t.write("run-5", "k", {"a": 1})
        key = store.put.call_args[0][0]
        assert key.startswith("myns/")


class TestObjectStoreTransportExists(unittest.IsolatedAsyncioTestCase):
    async def test_exists_true_when_key_in_listing(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-6")
        handle = await t.write("run-6", "k", {"a": 1})

        async def _list_with_key(prefix: str = "") -> AsyncIterator[str]:
            yield handle.key

        store.list = AsyncMock(side_effect=_list_with_key)
        assert await t.exists(handle)

    async def test_exists_false_when_key_absent(self) -> None:
        store = _make_store(keys=[])
        t = _transport(store)
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn/run-99/k/abc.bin",
            type_name="builtins.dict",
        )
        assert not await t.exists(handle)

    async def test_exists_false_on_store_exception(self) -> None:
        store = _make_store()
        store.list = AsyncMock(side_effect=RuntimeError("connection refused"))
        t = _transport(store)
        handle = TransportHandle(
            transport_id=t.transport_id,
            key="pirn/run-7/k/abc.bin",
            type_name="builtins.dict",
        )
        assert not await t.exists(handle)


class TestObjectStoreTransportEndRun(unittest.IsolatedAsyncioTestCase):
    async def test_end_run_deletes_all_written_keys(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-8")
        await t.write("run-8", "k1", {"a": 1})
        await t.write("run-8", "k2", {"b": 2})
        await t.end_run("run-8", success=True)
        assert store.delete.call_count == 2

    async def test_end_run_success_false_deletes_by_default(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-9")
        await t.write("run-9", "k", {"a": 1})
        await t.end_run("run-9", success=False)
        assert store.delete.call_count == 1

    async def test_end_run_keep_on_failure_skips_deletion(self) -> None:
        store = _make_store()
        t = _transport(store, keep_on_failure=True)
        await t.begin_run("run-10")
        await t.write("run-10", "k", {"a": 1})
        await t.end_run("run-10", success=False)
        store.delete.assert_not_called()

    async def test_end_run_keep_on_failure_still_deletes_on_success(self) -> None:
        store = _make_store()
        t = _transport(store, keep_on_failure=True)
        await t.begin_run("run-11")
        await t.write("run-11", "k", {"a": 1})
        await t.end_run("run-11", success=True)
        assert store.delete.call_count == 1

    async def test_end_run_no_keys_does_not_call_delete(self) -> None:
        store = _make_store()
        t = _transport(store)
        await t.begin_run("run-12")
        await t.end_run("run-12", success=True)
        store.delete.assert_not_called()
