"""Unit tests for :class:`MongoDBPool`.

Uses injected fakes — no real MongoDB or motor needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.mongodb_config import MongoDBConfig
from pirn.connectors.document.mongodb_pool import MongoDBPool

# ──────────────────────────────────────────────────────────── fakes


class FakeInsertOneResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class FakeInsertManyResult:
    def __init__(self, inserted_ids: list[str]) -> None:
        self.inserted_ids = inserted_ids


class FakeMotorCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    async def to_list(self, length: Any = None) -> list[dict[str, Any]]:
        return list(self._docs)


class FakeMotorCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.inserted: list[Any] = []
        self.bulk_inserted: list[Any] = []
        self._docs = docs or []

    async def insert_one(self, doc: Any) -> FakeInsertOneResult:
        self.inserted.append(doc)
        return FakeInsertOneResult("fake-id-001")

    def find(self, filter: Any = None) -> FakeMotorCursor:
        return FakeMotorCursor(self._docs)

    async def insert_many(self, docs: list[Any]) -> FakeInsertManyResult:
        self.bulk_inserted.extend(docs)
        return FakeInsertManyResult([f"id-{i}" for i in range(len(docs))])


class FakeMotorDB:
    def __init__(self) -> None:
        self._collections: dict[str, FakeMotorCollection] = {}

    def __getitem__(self, name: str) -> FakeMotorCollection:
        if name not in self._collections:
            self._collections[name] = FakeMotorCollection()
        return self._collections[name]

    def set_docs(self, collection: str, docs: list[dict[str, Any]]) -> None:
        self._collections[collection] = FakeMotorCollection(docs)


class FakeMotorClient:
    def __init__(self) -> None:
        self._db = FakeMotorDB()
        self.closed = False

    def __getitem__(self, name: str) -> FakeMotorDB:
        return self._db

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_pool(db_name: str = "testdb") -> tuple[MongoDBPool, FakeMotorClient]:
    config = MongoDBConfig(database=db_name)
    fake_client = FakeMotorClient()
    pool = MongoDBPool(config=config, client=fake_client)
    return pool, fake_client


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool, _ = make_pool()
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            MongoDBPool()
    
    
    def test_config_without_database_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "database must be non-empty"):
            MongoDBPool(config=MongoDBConfig(database=""))
    
    
# ───────────────────────────────────────────────────────────── operations


class TestOperations(unittest.IsolatedAsyncioTestCase):
    async def test_execute_inserts_document(self) -> None:
        pool, fake_client = make_pool()
        doc = {"name": "Alice", "age": 30}
        result = await pool.execute("users", doc)
        assert result == "fake-id-001"
        col = fake_client._db["users"]
        assert col.inserted == [doc]

    async def test_fetch_all_returns_documents_without_id(self) -> None:
        pool, fake_client = make_pool()
        fake_client._db.set_docs(
            "items",
            [{"_id": "abc", "name": "widget"}, {"_id": "def", "name": "gadget"}],
        )
        rows = await pool.fetch_all("items")
        assert rows == [{"name": "widget"}, {"name": "gadget"}]

    async def test_fetch_all_with_filter(self) -> None:
        pool, fake_client = make_pool()
        fake_client._db.set_docs("items", [{"_id": "x", "val": 1}])
        rows = await pool.fetch_all("items", {"val": 1})
        assert rows == [{"val": 1}]

    async def test_execute_many_bulk_inserts(self) -> None:
        pool, fake_client = make_pool()
        docs = [{"x": 1}, {"x": 2}, {"x": 3}]
        await pool.execute_many("records", docs)
        col = fake_client._db["records"]
        assert col.bulk_inserted == docs

    async def test_acquire_returns_db(self) -> None:
        pool, fake_client = make_pool()
        db = await pool.acquire()
        assert db is fake_client._db

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        db = await pool.acquire()
        await pool.release(db)  # should not raise


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_client(self) -> None:
        pool, fake_client = make_pool()
        await pool.close()
        assert fake_client.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MongoDBConfig(
            database="mydb",
            password="super-secret",
        )
        text = repr(cfg)
        assert "super-secret" not in text
        assert "<redacted>" in text

    def test_repr_redacts_uri(self) -> None:
        cfg = MongoDBConfig(
            uri="mongodb://alice:hunter2@db.example.com:27017",
            database="mydb",
        )
        text = repr(cfg)
        assert "hunter2" not in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MongoDBConfig(database="mydb", password="s3cr3t")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"

    def test_audit_dict_redacts_uri(self) -> None:
        cfg = MongoDBConfig(database="mydb", uri="mongodb://alice:hunter2@db.example.com:27017")
        d = cfg.to_audit_dict()
        assert d["uri"] == "<redacted>"
        assert "hunter2" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        pool, _ = make_pool()
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()
