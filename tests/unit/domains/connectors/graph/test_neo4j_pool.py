"""Unit tests for :class:`Neo4jPool`.

Uses injected stubs — no real Neo4j instance required. Real integration tests
live under ``tests/integration`` behind the ``needs_neo4j`` marker.
"""

from __future__ import annotations

import logging
import unittest
import unittest.mock
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.graph.neo4j_config import Neo4jConfig
from pirn.connectors.graph.neo4j_pool import Neo4jPool

# ──────────────────────────────────────────────────────────────── fakes


class FakeNeo4jResult:
    """Fake async result from session.run()."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def values(self) -> list[dict[str, Any]]:
        return self._records


class FakeNeo4jSession:
    """Mirrors the surface of a Neo4j async session."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.ran: list[tuple[str, dict[str, Any]]] = []
        self.closed = False
        self._records = records or []

    async def run(self, query: str, parameters: dict[str, Any]) -> FakeNeo4jResult:
        self.ran.append((query, parameters))
        return FakeNeo4jResult(self._records)

    async def close(self) -> None:
        self.closed = True


class FakeNeo4jDriver:
    """Mirrors the surface of a Neo4j async driver."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = records or []
        self.sessions: list[FakeNeo4jSession] = []
        self.closed = False

    def session(self, *, database: str | None = None) -> FakeNeo4jSession:
        s = FakeNeo4jSession(self._records)
        self.sessions.append(s)
        return s

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = Neo4jPool(driver=FakeNeo4jDriver())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_driver(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or driver="):
            Neo4jPool()
    
    
# ────────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_delegates_query_and_params(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(
            Neo4jConfig(database="neo4j"),
            driver=fake,
        )
        await pool.execute("CREATE (n:Node {id: $id})", {"id": 1})
        assert len(fake.sessions) == 1
        session = fake.sessions[0]
        assert session.ran == [("CREATE (n:Node {id: $id})", {"id": 1})]

    async def test_execute_no_params(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        await pool.execute("MATCH (n) DETACH DELETE n")
        session = fake.sessions[0]
        assert session.ran == [("MATCH (n) DETACH DELETE n", {})]

    async def test_execute_rejects_too_many_positional_args(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        with self.assertRaisesRegex(ValueError, "at most one"):
            await pool.execute("QUERY", {"a": 1}, {"b": 2})

    async def test_fetch_all_returns_records_as_dicts(self) -> None:
        records = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        fake = FakeNeo4jDriver(records=records)
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        result = await pool.fetch_all("MATCH (n) RETURN n.id AS id, n.name AS name")
        assert result == records

    async def test_execute_many_runs_each_item(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        await pool.execute_many(
            "CREATE (n:Node {id: $id})",
            [{"id": 1}, {"id": 2}, {"id": 3}],
        )
        # One session per execute call.
        assert len(fake.sessions) == 3

    async def test_acquire_returns_session(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        session = await pool.acquire()
        assert isinstance(session, FakeNeo4jSession)

    async def test_release_closes_session(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(Neo4jConfig(database="neo4j"), driver=fake)
        session = await pool.acquire()
        assert not session.closed
        await pool.release(session)
        assert session.closed


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_driver(self) -> None:
        fake = FakeNeo4jDriver()
        pool = Neo4jPool(driver=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = Neo4jPool(driver=FakeNeo4jDriver())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = Neo4jPool(config=Neo4jConfig(database="neo4j"), driver=FakeNeo4jDriver())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = Neo4jPool(config=Neo4jConfig(database="neo4j"), driver=FakeNeo4jDriver())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ──────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = Neo4jConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="super-secret",
        )
        assert "super-secret" not in repr(cfg)
        assert "<redacted>" in repr(cfg)

    def test_audit_dict_redacts_password(self) -> None:
        cfg = Neo4jConfig(password="my-db-password")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "my-db-password" not in str(d)

    def test_repr_shows_uri_and_user(self) -> None:
        cfg = Neo4jConfig(uri="bolt://db.example.com:7687", user="admin")
        text = repr(cfg)
        assert "bolt://db.example.com:7687" in text
        assert "admin" in text


class TestConnectErrorScrubs(unittest.IsolatedAsyncioTestCase):
    async def test_connect_error_scrubs_password(self) -> None:
        import sys

        fake_neo4j = type("FakeNeo4j", (), {})()

        class FakeAsyncGraphDatabase:
            @staticmethod
            def driver(*args: Any, **kwargs: Any) -> None:
                raise ConnectionError(
                    "could not connect: bolt://neo4j:secret-pw@localhost:7687 timed out"
                )

        fake_neo4j.AsyncGraphDatabase = FakeAsyncGraphDatabase  # type: ignore[attr-defined]
        with unittest.mock.patch.dict(sys.modules, {"neo4j": fake_neo4j}):
            pool = Neo4jPool(
                Neo4jConfig(uri="bolt://localhost:7687", password="secret-pw")
            )
            with self.assertRaises(ConnectionError) as exc_info:
                await pool.acquire()
        msg = str(exc_info.exception)
        assert "secret-pw" not in msg


# ────────────────────────────────────────────────────────────── log events


class TestLogEvents(unittest.IsolatedAsyncioTestCase):
    async def test_close_emits_debug_log(self) -> None:
        pool = Neo4jPool(driver=FakeNeo4jDriver())
        with self.assertLogs(level=logging.DEBUG) as cm:
            await pool.close()
        assert any("neo4j.close" in r for r in cm.output)
