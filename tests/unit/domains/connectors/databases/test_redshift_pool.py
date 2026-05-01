"""Unit tests for :class:`RedshiftPool`.

Uses an injected stub pool that mirrors the asyncpg ``Pool`` surface — no
real Redshift cluster needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.redshift_config import RedshiftConfig
from pirn.domains.connectors.databases.redshift_pool import RedshiftPool


# ──────────────────────────────────────────────────────────── fake pool


class FakeAsyncpgPool:
    """Mirrors the surface of ``asyncpg.Pool`` that RedshiftPool calls into."""

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

    async def executemany(
        self, query: str, args_seq: list[tuple[Any, ...]]
    ) -> None:
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


def test_implements_database_connection_pool() -> None:
    pool = RedshiftPool(pool=FakeAsyncpgPool())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_pool() -> None:
    with pytest.raises(TypeError, match="config= or pool="):
        RedshiftPool()


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_passes_query_and_args(self) -> None:
        fake = FakeAsyncpgPool()
        pool = RedshiftPool(pool=fake)
        await pool.execute(
            "INSERT INTO t (x, y) VALUES ($1, $2)", 1, "hello"
        )
        assert fake.executed == [
            ("INSERT INTO t (x, y) VALUES ($1, $2)", (1, "hello"))
        ]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAsyncpgPool()
        fake.fetch_responses["SELECT id FROM t WHERE x = $1"] = [(1,), (2,)]
        pool = RedshiftPool(pool=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = $1", 99)
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAsyncpgPool()
        pool = RedshiftPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES ($1, $2)",
            [(1, "a"), (2, "b"), (3, "c")],
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES ($1, $2)", [(1, "a"), (2, "b"), (3, "c")])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAsyncpgPool()
        pool = RedshiftPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety:
    def test_rejects_fstring_placeholder(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_dollar_placeholder(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = $1")


@pytest.mark.asyncio
class TestQuerySafetyEnforced:
    async def test_execute_rejects_format_query(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.execute("SELECT %s FROM t", "x")

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAsyncpgPool()
        pool = RedshiftPool(pool=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = RedshiftPool(pool=FakeAsyncpgPool())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


# ─────────────────────────────────────────────────────────────── DSN safety


class TestDsnLogSafety:
    def test_repr_redacts_password_field(self) -> None:
        cfg = RedshiftConfig(
            host="redshift.example.com",
            user="alice",
            password="hunter-2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter-2-leaks" not in text
        assert "<redacted>" in text

    def test_repr_scrubs_dsn_string_field(self) -> None:
        cfg = RedshiftConfig(dsn="postgres://alice:hunter2@db/main")
        assert "hunter2" not in repr(cfg)
        assert "<redacted>" in repr(cfg)


@pytest.mark.asyncio
class TestConnectErrorScrubs:
    async def test_connect_error_scrubs_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_asyncpg = type("FakeAsyncpg", (), {})()

        async def boom(*_: Any, **__: Any) -> None:
            raise ConnectionError(
                "could not connect: postgres://alice:secret-pw@db/main timed out"
            )

        fake_asyncpg.create_pool = boom  # type: ignore[attr-defined]
        monkeypatch.setitem(__import__("sys").modules, "asyncpg", fake_asyncpg)

        pool = RedshiftPool(
            RedshiftConfig(dsn="postgres://alice:secret-pw@db/main")
        )
        with pytest.raises(ConnectionError) as exc_info:
            await pool.acquire()
        msg = str(exc_info.value)
        assert "secret-pw" not in msg
        assert "<redacted>" in msg
