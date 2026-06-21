"""Unit tests for :class:`FirestorePool`.

Uses injected fakes — no real Firestore or google-cloud-firestore needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.firestore_config import FirestoreConfig
from pirn.connectors.document.firestore_pool import FirestorePool

# ──────────────────────────────────────────────────────────── fakes


class FakeDocRef:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class FakeDocSnapshot:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class FakeCollectionRef:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self._docs = docs or []
        self.added: list[Any] = []
        self._filters: list[tuple[str, str, Any]] = []

    async def add(self, doc: Any) -> tuple[Any, FakeDocRef]:
        self.added.append(doc)
        return (None, FakeDocRef("new-doc-id"))

    def where(self, field: str, op: str, value: Any) -> FakeCollectionRef:
        col = FakeCollectionRef(self._docs)
        col._filters = [*list(self._filters), (field, op, value)]
        return col

    def document(self) -> FakeDocRef:
        return FakeDocRef("batch-doc-id")

    def stream(self) -> FakeCollectionRef:
        return self

    def __aiter__(self) -> FakeCollectionRef:
        self._iter = iter(self._docs)
        return self

    async def __anext__(self) -> FakeDocSnapshot:
        try:
            return FakeDocSnapshot(next(self._iter))
        except StopIteration:
            raise StopAsyncIteration from None


class FakeBatch:
    def __init__(self) -> None:
        self.operations: list[tuple[Any, Any]] = []
        self.committed = False

    def set(self, doc_ref: Any, data: Any) -> None:
        self.operations.append((doc_ref, data))

    async def commit(self) -> None:
        self.committed = True


class FakeFirestoreClient:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self._docs = docs or []
        self._batch = FakeBatch()
        self.closed = False

    def collection(self, path: str) -> FakeCollectionRef:
        return FakeCollectionRef(self._docs)

    def batch(self) -> FakeBatch:
        return self._batch

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_pool(
    docs: list[dict[str, Any]] | None = None,
) -> tuple[FirestorePool, FakeFirestoreClient]:
    config = FirestoreConfig(project_id="my-project")
    fake_client = FakeFirestoreClient(docs)
    pool = FirestorePool(config=config, client=fake_client)
    return pool, fake_client


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool, _ = make_pool()
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            FirestorePool()
    
    
    def test_config_requires_non_empty_project_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "project_id must be non-empty"):
            FirestoreConfig(project_id="")
    
    
# ───────────────────────────────────────────────────────────── operations


class TestOperations(unittest.IsolatedAsyncioTestCase):
    async def test_execute_adds_document(self) -> None:
        pool, _fake_client = make_pool()
        doc = {"name": "Alice", "age": 30}
        result = await pool.execute("users", doc)
        assert result == "new-doc-id"

    async def test_fetch_all_returns_documents(self) -> None:
        docs = [{"name": "Alice"}, {"name": "Bob"}]
        pool, _ = make_pool(docs)
        result = await pool.fetch_all("users")
        assert result == docs

    async def test_fetch_all_with_filter(self) -> None:
        docs = [{"name": "Alice", "active": True}]
        pool, _ = make_pool(docs)
        result = await pool.fetch_all("users", {"active": True})
        assert result == docs

    async def test_execute_many_batch_commits(self) -> None:
        pool, fake_client = make_pool()
        docs = [{"x": 1}, {"x": 2}]
        await pool.execute_many("records", docs)
        assert fake_client._batch.committed is True
        assert len(fake_client._batch.operations) == 2

    async def test_acquire_returns_client(self) -> None:
        pool, fake_client = make_pool()
        client = await pool.acquire()
        assert client is fake_client

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        client = await pool.acquire()
        await pool.release(client)  # should not raise


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
    def test_repr_redacts_credentials_json(self) -> None:
        cfg = FirestoreConfig(
            project_id="my-project",
            credentials_json='{"private_key": "super-secret-key"}',
        )
        text = repr(cfg)
        assert "super-secret-key" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_credentials_json(self) -> None:
        cfg = FirestoreConfig(
            project_id="my-project",
            credentials_json='{"private_key": "s3cr3t"}',
        )
        d = cfg.to_audit_dict()
        assert d["credentials_json"] == "<redacted>"


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
