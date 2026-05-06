"""Unit tests for :class:`MySQLPool`.

Uses an injected stub aiomysql-shaped pool — no real MySQL server or
aiomysql driver installation required.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.mysql_config import MySQLConfig
from pirn.domains.connectors.databases.mysql_pool import MySQLPool

# ──────────────────────────────────────────────────────────── fake pool


class FakeMysqlCursor:
    def __init__(
        self, parent: FakeMysqlConnection
    ) -> None:
        self._parent = parent
        self._last_query: str | None = None
        self.rowcount = 0
        self.closed = False

    async def execute(self, query: str, params: list[Any]) -> None:
        self._parent.parent_pool.executed.append((query, list(params)))
        self._last_query = query
        self.rowcount = 1

    async def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._parent.parent_pool.executed_many.append(
            (query, [list(r) for r in rows])
        )
        self.rowcount = len(rows)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self._parent.parent_pool.responses.get(self._last_query or "", [])

    async def close(self) -> None:
        self.closed = True


class FakeMysqlConnection:
    def __init__(self, parent_pool: FakeAiomysqlPool) -> None:
        self.parent_pool = parent_pool
        self.committed = 0

    async def cursor(self) -> FakeMysqlCursor:
        return FakeMysqlCursor(self)

    async def commit(self) -> None:
        self.committed += 1


class FakeAiomysqlPool:
    """Mirrors ``aiomysql.Pool`` surface."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.acquired: list[FakeMysqlConnection] = []
        self.released: list[FakeMysqlConnection] = []
        self.closed = False
        self.waited = False

    async def acquire(self) -> FakeMysqlConnection:
        conn = FakeMysqlConnection(self)
        self.acquired.append(conn)
        return conn

    async def release(self, conn: FakeMysqlConnection) -> None:
        self.released.append(conn)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            MySQLPool()
    
    
    def test_construction_rejects_bogus_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "MySQLConfig"):
            MySQLPool(config="not-a-config")  # type: ignore[arg-type]
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.execute(
            "INSERT INTO t (x, y) VALUES (%s, %s)", [1, "hello"]
        )
        assert fake.executed == [
            ("INSERT INTO t (x, y) VALUES (%s, %s)", [1, "hello"])
        ]
        # connection acquired and released
        assert len(fake.acquired) == 1
        assert fake.released == fake.acquired

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAiomysqlPool()
        fake.responses["SELECT id FROM t WHERE x = %s"] = [(1,), (2,)]
        pool = MySQLPool(pool=fake)
        rows = await pool.fetch_all(
            "SELECT id FROM t WHERE x = %s", [99]
        )
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (%s, %s)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (%s, %s)", [[1, "a"], [2, "b"]])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_accepts_percent_s_placeholder(self) -> None:
        # ``%s`` is the canonical MySQL placeholder, not interpolation.
        pool = MySQLPool(pool=FakeAiomysqlPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_brace_query(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT * FROM t WHERE x = {evil}", [])

    async def test_fetch_all_rejects_brace_query(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.close()
        assert fake.closed is True
        assert fake.waited is True

    async def test_close_is_idempotent(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MySQLConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MySQLConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["host"] == "db.example.com"
        assert d["user"] == "alice"

    def test_password_listed_in_sensitive_fields(self) -> None:
        assert "password" in MySQLConfig.sensitive_fields
