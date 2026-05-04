"""Unit tests for :class:`KdbPool`.

Uses an injected synchronous stub connection — no real kdb+ needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.timeseries.kdb_config import KdbConfig
from pirn.domains.connectors.timeseries.kdb_pool import KdbPool


# ──────────────────────────────────────────────────────────── fake connection


class FakeKdbConnection:
    """Mirrors the sync kdb+ connection surface (pykx / qpython)."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._responses = responses or {}
        self.closed = False

    def sync(self, query: str, *args: Any) -> Any:
        self.calls.append((query, args))
        return self._responses.get(query, "OK")

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = KdbPool(connection=FakeKdbConnection())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_connection() -> None:
    with pytest.raises(TypeError, match="config= or connection="):
        KdbPool()


# ───────────────────────────────────────────────────────────── config


def test_config_repr_redacts_password() -> None:
    cfg = KdbConfig(password="s3cr3t")
    assert "s3cr3t" not in repr(cfg)
    assert "<redacted>" in repr(cfg)


# ───────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_returns_string_result(self) -> None:
        fake = FakeKdbConnection(responses={"1+1": 2})
        pool = KdbPool(connection=fake)
        result = await pool.execute("1+1")
        assert result == "2"
        assert fake.calls == [("1+1", ())]

    async def test_execute_passes_args(self) -> None:
        fake = FakeKdbConnection(responses={"select from t where sym=$1": "rows"})
        pool = KdbPool(connection=fake)
        await pool.execute("select from t where sym=$1", "AAPL")
        assert fake.calls == [("select from t where sym=$1", ("AAPL",))]

    async def test_fetch_all_wraps_scalar_in_list(self) -> None:
        fake = FakeKdbConnection(responses={"q": "scalar"})
        pool = KdbPool(connection=fake)
        rows = await pool.fetch_all("q")
        assert rows == ["scalar"]

    async def test_fetch_all_converts_table_rows(self) -> None:
        # Simulate a pykx-style table (iterable of dict-like rows)
        class FakeRow(dict):
            pass

        table = [FakeRow(sym="AAPL", price=150.0), FakeRow(sym="MSFT", price=300.0)]
        fake = FakeKdbConnection(responses={"select from trade": table})
        pool = KdbPool(connection=fake)
        rows = await pool.fetch_all("select from trade")
        assert rows == [{"sym": "AAPL", "price": 150.0}, {"sym": "MSFT", "price": 300.0}]

    async def test_acquire_returns_connection(self) -> None:
        fake = FakeKdbConnection()
        pool = KdbPool(connection=fake)
        conn = await pool.acquire()
        assert conn is fake

    async def test_execute_many_loops(self) -> None:
        fake = FakeKdbConnection()
        pool = KdbPool(connection=fake)
        await pool.execute_many("insert into t", [("a",), ("b",)])
        assert fake.calls == [("insert into t", ("a",)), ("insert into t", ("b",))]


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_calls_connection_close(self) -> None:
        fake = FakeKdbConnection()
        pool = KdbPool(connection=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = KdbPool(connection=FakeKdbConnection())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = KdbPool(config=KdbConfig(), connection=FakeKdbConnection())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = KdbPool(config=KdbConfig(), connection=FakeKdbConnection())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


class TestCredentialSafety:
    def test_audit_dict_redacts_password(self) -> None:
        cfg = KdbConfig(password="supersecret")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "supersecret" not in str(d)
