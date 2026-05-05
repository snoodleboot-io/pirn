"""Tests for the four connector interfaces.

Each interface raises :class:`NotImplementedError` from every method when
not overridden. This file pins those contracts so a future change that
silently drops an interface method is caught.
"""

from __future__ import annotations
import unittest


from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.object_store import ObjectStore


class TestDatabaseConnectionPoolInterface(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "acquire"):
            await DatabaseConnectionPool().acquire()

    async def test_release_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "release"):
            await DatabaseConnectionPool().release(object())

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
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


class TestObjectStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_get_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "get"):
            await ObjectStore().get("k")

    async def test_put_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "put"):
            await ObjectStore().put("k", b"v")

    async def test_delete_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "delete"):
            await ObjectStore().delete("k")

    async def test_list_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "list"):
            await ObjectStore().list()


class TestMessageBrokerInterface(unittest.IsolatedAsyncioTestCase):
    async def test_publish_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "publish"):
            await MessageBroker().publish("t", b"v")

    async def test_consume_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "consume"):
            await MessageBroker().consume("t")


class TestFileFormatInterfaceSync(unittest.TestCase):
    def test_name_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "name"):
            _ = FileFormat().name


class TestFileFormatInterface(unittest.IsolatedAsyncioTestCase):
    async def test_read_raises_not_implemented(self) -> None:
        async def empty():
            if False:
                yield b""

        with self.assertRaisesRegex(NotImplementedError, "read"):
            await FileFormat().read(empty())

    async def test_write_raises_not_implemented(self) -> None:
        async def empty():
            if False:
                yield b""

        with self.assertRaisesRegex(NotImplementedError, "write"):
            await FileFormat().write(empty())
