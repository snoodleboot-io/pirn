"""Unit tests for :class:`CouchbasePool`.

Uses injected fakes — no real Couchbase SDK needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.couchbase_config import CouchbaseConfig
from pirn.domains.connectors.document.couchbase_pool import CouchbasePool

# ──────────────────────────────────────────────────────────── fakes


class FakeMeta:
    def status(self) -> str:
        return "success"


class FakeCouchbaseResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def meta_data(self) -> FakeMeta:
        return FakeMeta()

    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)


class FakeCouchbaseCluster:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []
        self.queries: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def query(self, query: str, *args: Any) -> FakeCouchbaseResult:
        self.queries.append((query, args))
        return FakeCouchbaseResult(self._rows)

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_pool(
    rows: list[dict[str, Any]] | None = None,
) -> tuple[CouchbasePool, FakeCouchbaseCluster]:
    config = CouchbaseConfig(bucket="test-bucket")
    fake_cluster = FakeCouchbaseCluster(rows)
    pool = CouchbasePool(config=config, cluster=fake_cluster)
    return pool, fake_cluster


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool, _ = make_pool()
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_cluster(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or cluster="):
            CouchbasePool()
    
    
    def test_config_requires_non_empty_bucket(self) -> None:
        with self.assertRaisesRegex(ValueError, "bucket must be non-empty"):
            CouchbaseConfig(bucket="")
    
    
# ───────────────────────────────────────────────────────────── operations


class TestOperations(unittest.IsolatedAsyncioTestCase):
    async def test_execute_returns_status_string(self) -> None:
        pool, fake_cluster = make_pool()
        result = await pool.execute("SELECT * FROM `test-bucket`")
        assert isinstance(result, str)
        assert fake_cluster.queries[0][0] == "SELECT * FROM `test-bucket`"

    async def test_fetch_all_returns_rows(self) -> None:
        rows = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        pool, _ = make_pool(rows)
        result = await pool.fetch_all("SELECT * FROM `test-bucket`")
        assert result == rows

    async def test_execute_many_runs_for_each(self) -> None:
        pool, fake_cluster = make_pool()
        await pool.execute_many(
            "SELECT * FROM `test-bucket` WHERE id = $1",
            [("id-1",), ("id-2",)],
        )
        assert len(fake_cluster.queries) == 2

    async def test_acquire_returns_cluster(self) -> None:
        pool, fake_cluster = make_pool()
        cluster = await pool.acquire()
        assert cluster is fake_cluster

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        cluster = await pool.acquire()
        await pool.release(cluster)  # should not raise


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_cluster(self) -> None:
        pool, fake_cluster = make_pool()
        await pool.close()
        assert fake_cluster.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = CouchbaseConfig(bucket="mybucket", password="super-secret")
        text = repr(cfg)
        assert "super-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = CouchbaseConfig(bucket="mybucket", password="s3cr3t")
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
