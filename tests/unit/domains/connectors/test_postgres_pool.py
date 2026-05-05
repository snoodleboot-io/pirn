"""Unit tests for :class:`PostgresPool`.

Uses an injected stub pool that mirrors the asyncpg ``Pool`` surface — no
real Postgres needed. Real-Postgres integration tests live under
``tests/integration`` behind the ``needs_postgres`` marker.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock
import unittest


from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.postgres_config import PostgresConfig
from pirn.domains.connectors.databases.postgres_pool import PostgresPool


# ──────────────────────────────────────────────────────────── fake pool


class FakeAsyncpgPool:
    """Mirrors the surface of ``asyncpg.Pool`` that PostgresPool calls into."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.executed_many: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.fetch_responses: dict[str, list[Any]] = {}
        self.acquired: list[object] = []
        self.released: list[object] = []
        self.closed = False

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "EXECUTE OK"

    async def executemany(self, query: str, args_seq: list[tuple[Any, ...]]) -> None:
        self.executed_many.append((query, list(args_seq)))

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.executed.append((query, args))
        return self.fetch_responses.get(query, [])

    async def acquire(self) -> Any:
        conn = object()
        self.acquired.append(conn)
        return conn

    async def release(self, conn: Any) -> None:
        self.released.append(conn)

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            PostgresPool()
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_args(self) -> None:
        fake = FakeAsyncpgPool()
        pool = PostgresPool(pool=fake)
        await pool.execute(
            "INSERT INTO t (x, y) VALUES ($1, $2)", 1, "hello"
        )
        assert fake.executed == [
            ("INSERT INTO t (x, y) VALUES ($1, $2)", (1, "hello"))
        ]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAsyncpgPool()
        fake.fetch_responses["SELECT id FROM t WHERE x = $1"] = [(1,), (2,)]
        pool = PostgresPool(pool=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = $1", 99)
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAsyncpgPool()
        pool = PostgresPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES ($1, $2)",
            [(1, "a"), (2, "b"), (3, "c")],
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES ($1, $2)", [(1, "a"), (2, "b"), (3, "c")])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAsyncpgPool()
        pool = PostgresPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {value}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_dollar_placeholder(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = $1")  # no raise


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", "x")

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAsyncpgPool()
        pool = PostgresPool(pool=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = PostgresPool(pool=FakeAsyncpgPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── DSN safety


class TestDsnLogSafety(unittest.TestCase):
    """The PostgresConfig.repr/audit must not leak credentials, even when
    the user passes a full DSN with inline password."""

    def test_repr_redacts_password_field(self) -> None:
        cfg = PostgresConfig(
            host="db.example.com",
            port=5432,
            user="alice",
            password="hunter-2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter-2-leaks" not in text
        assert "<redacted>" in text

    def test_repr_scrubs_dsn_string_field(self) -> None:
        cfg = PostgresConfig(dsn="postgres://alice:hunter2@db/main")
        assert "hunter2" not in repr(cfg)
        assert "<redacted>" in repr(cfg)

    def test_audit_dict_redacts_both_password_and_dsn(self) -> None:
        cfg = PostgresConfig(
            dsn="postgres://alice:dsn-pw@db/main",
            password="field-pw",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "dsn-pw" not in d["dsn"]
        assert "<redacted>" in d["dsn"]


class TestConnectErrorScrubs(unittest.IsolatedAsyncioTestCase):
    """If asyncpg raises with the password embedded in the error message,
    we must scrub before re-raising — protecting the no-leak quality bar."""

    async def test_connect_error_scrubs_password(self) -> None:
        # Inject a fake asyncpg.create_pool that raises with the password
        # echoed back in the error message — a known asyncpg behaviour.
        fake_asyncpg = type("FakeAsyncpg", (), {})()

        async def boom(*_: Any, **__: Any) -> None:
            raise ConnectionError(
                "could not connect: postgres://alice:secret-pw@db/main timed out"
            )

        fake_asyncpg.create_pool = boom  # type: ignore[attr-defined]
        with unittest.mock.patch.dict(__import__("sys").modules, {"asyncpg": fake_asyncpg}):
            pool = PostgresPool(
                PostgresConfig(dsn="postgres://alice:secret-pw@db/main")
            )
            with self.assertRaises(ConnectionError) as exc_info:
                await pool.acquire()
        msg = str(exc_info.exception)
        assert "secret-pw" not in msg
        assert "<redacted>" in msg
