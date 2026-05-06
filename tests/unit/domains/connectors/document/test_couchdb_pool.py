"""Unit tests for :class:`CouchDBPool`.

Uses injected fakes — no real CouchDB or aiocouch needed.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.couchdb_config import CouchDBConfig
from pirn.domains.connectors.document.couchdb_pool import CouchDBPool

# ──────────────────────────────────────────────────────────── fakes


class FakeDoc:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self._data = {"_id": doc_id, **data}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    async def save(self) -> None:
        pass


class FakeCouchDB_DB:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self._saved: list[Any] = []
        self._bulk: list[Any] = []
        self._docs = docs or []

    async def create(self, doc_id: str, data: Any = None) -> FakeDoc:
        doc = FakeDoc(doc_id, data or {})
        self._saved.append(doc)
        return doc

    async def find(self, selector: Any) -> list[dict[str, Any]]:
        return list(self._docs)

    async def bulk_docs(self, docs: list[Any]) -> None:
        self._bulk.extend(docs)


class FakeCouchSession:
    def __init__(self, db: FakeCouchDB_DB | None = None) -> None:
        self._db = db or FakeCouchDB_DB()
        self.closed = False

    async def __getitem__(self, name: str) -> FakeCouchDB_DB:  # type: ignore[misc]
        return self._db

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_pool(
    db: FakeCouchDB_DB | None = None,
) -> tuple[CouchDBPool, FakeCouchSession]:
    config = CouchDBConfig(database="testdb")
    fake_session = FakeCouchSession(db)
    pool = CouchDBPool(config=config, session=fake_session)
    return pool, fake_session


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool, _ = make_pool()
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_session(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or session="):
            CouchDBPool()
    
    
# ───────────────────────────────────────────────────────────── operations


class TestOperations(unittest.IsolatedAsyncioTestCase):
    async def test_execute_saves_document(self) -> None:
        db = FakeCouchDB_DB()
        pool, _ = make_pool(db)
        result = await pool.execute("doc-001", {"name": "Alice"})
        assert result == "doc-001"
        assert len(db._saved) == 1

    async def test_fetch_all_returns_documents(self) -> None:
        docs = [{"name": "Alice"}, {"name": "Bob"}]
        db = FakeCouchDB_DB(docs=docs)
        pool, _ = make_pool(db)
        selector = json.dumps({"name": {"$exists": True}})
        result = await pool.fetch_all(selector)
        assert result == docs

    async def test_fetch_all_with_invalid_json_uses_default_selector(self) -> None:
        docs = [{"x": 1}]
        db = FakeCouchDB_DB(docs=docs)
        pool, _ = make_pool(db)
        result = await pool.fetch_all("not-valid-json")
        assert result == docs

    async def test_execute_many_bulk_saves(self) -> None:
        db = FakeCouchDB_DB()
        pool, _ = make_pool(db)
        docs = [{"a": 1}, {"a": 2}]
        await pool.execute_many("ignored", docs)
        assert db._bulk == docs

    async def test_acquire_returns_session(self) -> None:
        pool, fake_session = make_pool()
        session = await pool.acquire()
        assert session is fake_session

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        session = await pool.acquire()
        await pool.release(session)  # should not raise


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_session(self) -> None:
        pool, fake_session = make_pool()
        await pool.close()
        assert fake_session.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = CouchDBConfig(password="super-secret")
        text = repr(cfg)
        assert "super-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = CouchDBConfig(password="s3cr3t")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"


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
