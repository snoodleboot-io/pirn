"""Unit tests for :class:`ClickhousePool`.

Uses an injected stub client mirroring the slice of
``clickhouse_connect.Client`` the pool calls into.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.clickhouse_config import ClickhouseConfig
from pirn.domains.connectors.databases.clickhouse_pool import ClickhousePool


# ──────────────────────────────────────────────────────────── fake client


class FakeClickhouseQueryResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_rows = list(rows)


class FakeClickhouseClient:
    """Mirrors the surface of ``clickhouse_connect.Client``."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, Any]] = []
        self.queries: list[tuple[str, Any]] = []
        self.inserts: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.closed = False

    def command(self, sql: str, parameters: Any = None) -> Any:
        self.commands.append((sql, parameters))
        return None

    def query(self, sql: str, parameters: Any = None) -> FakeClickhouseQueryResult:
        self.queries.append((sql, parameters))
        return FakeClickhouseQueryResult(self.responses.get(sql, []))

    def insert(self, table_or_sql: str, rows: list[list[Any]]) -> None:
        self.inserts.append((table_or_sql, [list(r) for r in rows]))

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = ClickhousePool(client=FakeClickhouseClient())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        ClickhousePool()


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeClickhouseClient()
        pool = ClickhousePool(client=fake)
        await pool.execute(
            "INSERT INTO t (x) VALUES ({x:Int64})", {"x": 1}
        )
        assert fake.commands == [
            ("INSERT INTO t (x) VALUES ({x:Int64})", {"x": 1})
        ]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeClickhouseClient()
        fake.responses["SELECT id FROM t WHERE x = {x:Int64}"] = [(1,), (2,)]
        pool = ClickhousePool(client=fake)
        rows = await pool.fetch_all(
            "SELECT id FROM t WHERE x = {x:Int64}", {"x": 99}
        )
        assert rows == [(1,), (2,)]

    async def test_execute_many_uses_insert(self) -> None:
        fake = FakeClickhouseClient()
        pool = ClickhousePool(client=fake)
        await pool.execute_many("INSERT INTO t", [(1, "a"), (2, "b")])
        assert fake.inserts == [("INSERT INTO t", [[1, "a"], [2, "b"]])]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety:
    def test_rejects_bare_fstring_placeholder(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation(
                "SELECT * FROM t WHERE x = {value}"
            )

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_typed_clickhouse_placeholder(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        pool._reject_inline_interpolation(
            "SELECT * FROM t WHERE x = {value:String}"
        )


@pytest.mark.asyncio
class TestQuerySafetyEnforced:
    async def test_execute_rejects_format_query(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeClickhouseClient()
        pool = ClickhousePool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = ClickhousePool(client=FakeClickhouseClient())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_password(self) -> None:
        cfg = ClickhouseConfig(
            host="ch.example.com",
            username="alice",
            password="hunter2-leaks",
            database="analytics",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = ClickhouseConfig(
            host="ch.example.com",
            username="alice",
            password="hunter2-leaks",
            database="analytics",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["host"] == "ch.example.com"
