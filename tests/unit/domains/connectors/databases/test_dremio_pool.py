"""Unit tests for :class:`DremioPool`.

Uses an injected stub Flight connection. No Dremio server needed.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.dremio_config import DremioConfig
from pirn.domains.connectors.databases.dremio_pool import DremioPool


# ──────────────────────────────────────────────────────────── fake connection


class FakeFlightAction:
    def __init__(self, body: bytes) -> None:
        self.body = _FakeBody(body)


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def to_pybytes(self) -> bytes:
        return self._data


class FakeBatch:
    def __init__(self, rows: list[dict]) -> None:
        columns = list(rows[0].keys()) if rows else []
        self._columns = columns
        self._rows = rows

        class _Schema:
            names = columns

        class _Column:
            def __init__(self, values: list) -> None:
                self._values = values

            def __getitem__(self, i: int) -> "_PyValue":
                return _PyValue(self._values[i])

        class _PyValue:
            def __init__(self, v: Any) -> None:
                self._v = v

            def as_py(self) -> Any:
                return self._v

        class _Table:
            schema = _Schema()
            num_rows = len(rows)

            def __init__(self, rows: list[dict], columns: list[str]) -> None:
                self._rows = rows
                self._columns = columns

            def column(self, name: str) -> _Column:
                return _Column([row[name] for row in self._rows])

        self.data = _Table(rows, columns)


class FakeFlightInfo:
    def __init__(self, batches: list[FakeBatch]) -> None:
        self.endpoints = [_FakeEndpoint(b) for b in batches]


class _FakeEndpoint:
    def __init__(self, batch: FakeBatch) -> None:
        self.ticket = batch


class FakeDremioConnection:
    """Minimal ``pyarrow.flight.FlightClient`` stub."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.calls: list[str] = []
        self._rows = rows or [{"id": 1, "name": "Alice"}]
        self.closed = False

    def do_get(self, ticket: Any) -> "list[FakeBatch]":
        self.calls.append("do_get")
        return [ticket]

    def do_action(self, action: Any) -> "list[FakeFlightAction]":
        self.calls.append("do_action")
        return [FakeFlightAction(b"1")]

    def get_flight_info(self, descriptor: Any) -> FakeFlightInfo:
        self.calls.append("get_flight_info")
        return FakeFlightInfo([FakeBatch(self._rows)])

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = DremioPool(connection=FakeDremioConnection())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_connection(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or connection="):
            DremioPool()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = DremioConfig()
        assert "password" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── acquire/release


class TestAcquireRelease(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_returns_connection(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        conn = await pool.acquire()
        assert conn is fake

    async def test_release_is_noop(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        conn = await pool.acquire()
        await pool.release(conn)


# ────────────────────────────────────────────────────────────── execute


class TestExecute(unittest.IsolatedAsyncioTestCase):
    async def test_execute_runs_action(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        result = await pool.execute("CREATE TABLE t (id INT)")
        assert isinstance(result, str)
        assert "do_action" in fake.calls

    async def test_execute_rejects_interpolation(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT * FROM t WHERE id = {id}")


# ────────────────────────────────────────────────────────────── fetch_all


class TestFetchAll(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_all_returns_list_of_dicts(self) -> None:
        fake = FakeDremioConnection(rows=[{"id": 1, "name": "Alice"}])
        pool = DremioPool(connection=fake)
        rows = await pool.fetch_all("SELECT id, name FROM users")
        assert isinstance(rows, list)
        assert rows[0]["name"] == "Alice"

    async def test_fetch_all_rejects_interpolation(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE name = %s")


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_connection(self) -> None:
        fake = FakeDremioConnection()
        pool = DremioPool(connection=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = DremioPool(connection=FakeDremioConnection())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = DremioPool(connection=FakeDremioConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = DremioPool(config=DremioConfig(), connection=FakeDremioConnection())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = DremioPool(config=DremioConfig(), connection=FakeDremioConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_execute_after_close_raises(self) -> None:
        pool = DremioPool(connection=FakeDremioConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.execute("SELECT 1")

    async def test_fetch_all_after_close_raises(self) -> None:
        pool = DremioPool(connection=FakeDremioConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.fetch_all("SELECT 1")


class TestCredentialSafety(unittest.TestCase):
    def test_audit_dict_redacts_password(self) -> None:
        cfg = DremioConfig(password="supersecret")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "supersecret" not in str(d)
