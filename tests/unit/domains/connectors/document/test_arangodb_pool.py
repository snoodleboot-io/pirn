"""Unit tests for :class:`ArangoDBPool`.

Uses injected fakes — no real ArangoDB or python-arango needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.arangodb_config import ArangoDBConfig
from pirn.connectors.document.arangodb_pool import ArangoDBPool

# ──────────────────────────────────────────────────────────── fakes


class FakeArangoAQL:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def execute(self, query: str, bind_vars: Any = None) -> list[dict[str, Any]]:
        self.executed.append((query, bind_vars or {}))
        return list(self._rows)


class FakeArangoDB:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.aql = FakeArangoAQL(rows)


# ───────────────────────────────────────────────────────────── helpers


def make_pool(rows: list[dict[str, Any]] | None = None) -> tuple[ArangoDBPool, FakeArangoDB]:
    fake_db = FakeArangoDB(rows)
    config = ArangoDBConfig(database="_system")
    pool = ArangoDBPool(config=config, db=fake_db)
    return pool, fake_db


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool, _ = make_pool()
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_db(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or db="):
            ArangoDBPool()
    
    
# ───────────────────────────────────────────────────────────── operations


class TestOperations(unittest.IsolatedAsyncioTestCase):
    async def test_execute_returns_string(self) -> None:
        pool, fake_db = make_pool()
        result = await pool.execute("FOR doc IN col RETURN doc", {"@col": "test"})
        assert isinstance(result, str)
        assert fake_db.aql.executed[0][0] == "FOR doc IN col RETURN doc"

    async def test_fetch_all_returns_rows(self) -> None:
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        pool, _ = make_pool(rows)
        result = await pool.fetch_all("FOR doc IN users RETURN doc")
        assert result == rows

    async def test_fetch_all_passes_bind_vars(self) -> None:
        pool, fake_db = make_pool()
        bind = {"@collection": "users"}
        await pool.fetch_all("FOR doc IN @@collection RETURN doc", bind)
        assert fake_db.aql.executed[0][1] == bind

    async def test_execute_many_runs_for_each(self) -> None:
        pool, fake_db = make_pool()
        await pool.execute_many(
            "INSERT @doc INTO col",
            [{"@doc": {"x": 1}}, {"@doc": {"x": 2}}],
        )
        assert len(fake_db.aql.executed) == 2

    async def test_acquire_returns_db(self) -> None:
        pool, fake_db = make_pool()
        db = await pool.acquire()
        assert db is fake_db

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        db = await pool.acquire()
        await pool.release(db)  # should not raise


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_marks_pool_closed(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        assert pool._closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = ArangoDBConfig(password="super-secret")
        text = repr(cfg)
        assert "super-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = ArangoDBConfig(password="s3cr3t")
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
