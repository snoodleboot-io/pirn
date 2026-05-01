"""Unit tests for :class:`DatabricksPool`.

Uses an injected stub client mirroring the cursor-based slice of
``databricks-sql-connector``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.databricks_config import DatabricksConfig
from pirn.domains.connectors.databases.databricks_pool import DatabricksPool


# ──────────────────────────────────────────────────────────── fake client


class FakeDatabricksCursor:
    def __init__(
        self, parent: FakeDatabricksClient
    ) -> None:  # noqa: F821 - forward ref OK
        self._parent = parent
        self._last_query: str | None = None
        self.rowcount = 0
        self.closed = False

    def execute(self, query: str, params: list[Any]) -> None:
        self._parent.executed.append((query, list(params)))
        self._last_query = query
        self.rowcount = 1

    def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._parent.executed_many.append((query, [list(r) for r in rows]))
        self.rowcount = len(rows)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._parent.responses.get(self._last_query or "", [])

    def close(self) -> None:
        self.closed = True


class FakeDatabricksClient:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.closed = False

    def cursor(self) -> FakeDatabricksCursor:
        return FakeDatabricksCursor(self)

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool = DatabricksPool(client=FakeDatabricksClient())
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        DatabricksPool()


# ────────────────────────────────────────────────────────── delegation


@pytest.mark.asyncio
class TestDelegation:
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeDatabricksClient()
        pool = DatabricksPool(client=fake)
        await pool.execute("INSERT INTO t (x) VALUES (?)", [1])
        assert fake.executed == [("INSERT INTO t (x) VALUES (?)", [1])]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeDatabricksClient()
        fake.responses["SELECT id FROM t WHERE x = ?"] = [(1,), (2,)]
        pool = DatabricksPool(client=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = ?", [99])
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeDatabricksClient()
        pool = DatabricksPool(client=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (?, ?)", [[1, "a"], [2, "b"]])
        ]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety:
    def test_rejects_fstring_placeholder(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_qmark_placeholder(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = ?")


@pytest.mark.asyncio
class TestQuerySafetyEnforced:
    async def test_execute_rejects_format_query(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        with pytest.raises(ValueError, match="interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeDatabricksClient()
        pool = DatabricksPool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = DatabricksPool(client=FakeDatabricksClient())
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_access_token(self) -> None:
        cfg = DatabricksConfig(
            server_hostname="adb-1.azuredatabricks.net",
            http_path="/sql/1.0/warehouses/abc",
            access_token="dapi-super-secret",
        )
        text = repr(cfg)
        assert "dapi-super-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_access_token(self) -> None:
        cfg = DatabricksConfig(
            server_hostname="adb-1.azuredatabricks.net",
            http_path="/sql/1.0/warehouses/abc",
            access_token="dapi-super-secret",
        )
        d = cfg.to_audit_dict()
        assert d["access_token"] == "<redacted>"
        assert d["server_hostname"] == "adb-1.azuredatabricks.net"
