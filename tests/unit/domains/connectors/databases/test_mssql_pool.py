"""Unit tests for :class:`MssqlPool`.

Uses an injected stub aioodbc-shaped pool — no real ODBC driver / SQL
Server installation needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.mssql_config import MssqlConfig
from pirn.domains.connectors.databases.mssql_pool import MssqlPool

# ──────────────────────────────────────────────────────────── fake pool


class FakeMssqlCursor:
    def __init__(
        self, parent: FakeMssqlConnection
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


class FakeMssqlConnection:
    def __init__(self, parent_pool: FakeAioodbcPool) -> None:
        self.parent_pool = parent_pool
        self.committed = 0

    async def cursor(self) -> FakeMssqlCursor:
        return FakeMssqlCursor(self)

    async def commit(self) -> None:
        self.committed += 1


class FakeAioodbcPool:
    """Mirrors ``aioodbc.Pool`` surface."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.acquired: list[FakeMssqlConnection] = []
        self.released: list[FakeMssqlConnection] = []
        self.closed = False
        self.waited = False

    async def acquire(self) -> FakeMssqlConnection:
        conn = FakeMssqlConnection(self)
        self.acquired.append(conn)
        return conn

    async def release(self, conn: FakeMssqlConnection) -> None:
        self.released.append(conn)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            MssqlPool()
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.execute("INSERT INTO t (x) VALUES (?)", [1])
        assert fake.executed == [("INSERT INTO t (x) VALUES (?)", [1])]
        # connection acquired and released
        assert len(fake.acquired) == 1
        assert fake.released == fake.acquired

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAioodbcPool()
        fake.responses["SELECT id FROM t WHERE x = ?"] = [(1,), (2,)]
        pool = MssqlPool(pool=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = ?", [99])
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (?, ?)", [[1, "a"], [2, "b"]])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_qmark_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = ?")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.close()
        assert fake.closed is True
        assert fake.waited is True

    async def test_close_is_idempotent(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["host"] == "db.example.com"

    def test_build_dsn_constructs_from_fields(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            port=1433,
            user="alice",
            password="pw",
            database="prod",
            driver="ODBC Driver 18 for SQL Server",
        )
        dsn = cfg.build_dsn()
        assert "db.example.com" in dsn
        assert "DATABASE=prod" in dsn
        assert "UID=alice" in dsn
        assert "PWD=pw" in dsn

    def test_build_dsn_returns_explicit_dsn_verbatim(self) -> None:
        provided = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=x;UID=u;PWD=p;"
        cfg = MssqlConfig(dsn=provided)
        assert cfg.build_dsn() == provided
