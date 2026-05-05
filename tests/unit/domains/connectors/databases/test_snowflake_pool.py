"""Unit tests for :class:`SnowflakePool`.

Uses an injected stub client that mirrors the cursor-based slice of the
``snowflake.connector`` API. No real Snowflake account needed.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.snowflake_config import SnowflakeConfig
from pirn.domains.connectors.databases.snowflake_pool import SnowflakePool


# ──────────────────────────────────────────────────────────── fake client


class FakeSnowflakeCursor:
    def __init__(
        self, parent: FakeSnowflakeClient
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


class FakeSnowflakeClient:
    """Mirrors the connection surface ``SnowflakePool`` calls into."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.closed = False

    def cursor(self) -> FakeSnowflakeCursor:
        return FakeSnowflakeCursor(self)

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            SnowflakePool()
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeSnowflakeClient()
        pool = SnowflakePool(client=fake)
        await pool.execute(
            "INSERT INTO t (x, y) VALUES (?, ?)", [1, "hello"]
        )
        assert fake.executed == [
            ("INSERT INTO t (x, y) VALUES (?, ?)", [1, "hello"])
        ]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeSnowflakeClient()
        fake.responses["SELECT id FROM t WHERE x = ?"] = [(1,), (2,)]
        pool = SnowflakePool(client=fake)
        rows = await pool.fetch_all(
            "SELECT id FROM t WHERE x = ?", [99]
        )
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeSnowflakeClient()
        pool = SnowflakePool(client=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (?, ?)", [[1, "a"], [2, "b"]])
        ]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_qmark_placeholder(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = ?")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeSnowflakeClient()
        pool = SnowflakePool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = SnowflakePool(client=FakeSnowflakeClient())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = SnowflakeConfig(
            account="xy12345",
            user="alice",
            password="hunter2-leaks",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = SnowflakeConfig(
            account="xy12345",
            user="alice",
            password="hunter2-leaks",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["account"] == "xy12345"
