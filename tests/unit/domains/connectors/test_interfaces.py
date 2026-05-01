"""Tests for the four connector interfaces.

Each interface raises :class:`NotImplementedError` from every method when
not overridden. This file pins those contracts so a future change that
silently drops an interface method is caught.
"""

from __future__ import annotations

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.object_store import ObjectStore


@pytest.mark.asyncio
class TestDatabaseConnectionPoolInterface:
    async def test_acquire_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="acquire"):
            await DatabaseConnectionPool().acquire()

    async def test_release_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="release"):
            await DatabaseConnectionPool().release(object())

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await DatabaseConnectionPool().close()

    async def test_subclass_satisfies_isinstance(self) -> None:
        class Concrete(DatabaseConnectionPool):
            async def acquire(self):
                return None
            async def release(self, conn):
                return None
            async def close(self):
                return None

        assert isinstance(Concrete(), DatabaseConnectionPool)


@pytest.mark.asyncio
class TestObjectStoreInterface:
    async def test_get_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="get"):
            await ObjectStore().get("k")

    async def test_put_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="put"):
            await ObjectStore().put("k", b"v")

    async def test_delete_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="delete"):
            await ObjectStore().delete("k")

    async def test_list_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="list"):
            await ObjectStore().list()


@pytest.mark.asyncio
class TestMessageBrokerInterface:
    async def test_publish_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="publish"):
            await MessageBroker().publish("t", b"v")

    async def test_consume_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="consume"):
            await MessageBroker().consume("t")


class TestFileFormatInterfaceSync:
    def test_name_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="name"):
            _ = FileFormat().name


@pytest.mark.asyncio
class TestFileFormatInterface:
    async def test_read_raises_not_implemented(self) -> None:
        async def empty():
            if False:
                yield b""

        with pytest.raises(NotImplementedError, match="read"):
            await FileFormat().read(empty())

    async def test_write_raises_not_implemented(self) -> None:
        async def empty():
            if False:
                yield b""

        with pytest.raises(NotImplementedError, match="write"):
            await FileFormat().write(empty())
