"""Unit tests for :class:`QuestDBPool`.

Uses an injected asyncpg-style stub — no real QuestDB needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.timeseries.questdb_config import QuestDBConfig
from pirn.domains.connectors.timeseries.questdb_pool import QuestDBPool

# ──────────────────────────────────────────────────────────── fake pool


class FakeAsyncpgPool:
    """Mirrors the asyncpg.Pool surface that QuestDBPool calls into."""

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
        pool = QuestDBPool(pool=FakeAsyncpgPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            QuestDBPool()
    
    
# ───────────────────────────────────────────────────────────── config


    def test_config_repr_redacts_password(self) -> None:
        cfg = QuestDBConfig(password="hunter-2-leaks")
        assert "hunter-2-leaks" not in repr(cfg)
        assert "<redacted>" in repr(cfg)
    
    
# ───────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_args(self) -> None:
        fake = FakeAsyncpgPool()
        pool = QuestDBPool(pool=fake)
        await pool.execute("INSERT INTO t (x, y) VALUES ($1, $2)", 1, "hello")
        assert fake.executed == [("INSERT INTO t (x, y) VALUES ($1, $2)", (1, "hello"))]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAsyncpgPool()
        fake.fetch_responses["SELECT id FROM t WHERE x = $1"] = [(1,), (2,)]
        pool = QuestDBPool(pool=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = $1", 99)
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAsyncpgPool()
        pool = QuestDBPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES ($1, $2)",
            [(1, "a"), (2, "b")],
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES ($1, $2)", [(1, "a"), (2, "b")])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAsyncpgPool()
        pool = QuestDBPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ───────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAsyncpgPool()
        pool = QuestDBPool(pool=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = QuestDBPool(pool=FakeAsyncpgPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = QuestDBPool(config=QuestDBConfig(), pool=FakeAsyncpgPool())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = QuestDBPool(config=QuestDBConfig(), pool=FakeAsyncpgPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


class TestCredentialSafety(unittest.TestCase):
    def test_audit_dict_redacts_password(self) -> None:
        cfg = QuestDBConfig(password="supersecret")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "supersecret" not in str(d)
