"""Unit tests for :class:`OrientDBPool`.

Uses injected stubs — no real OrientDB instance required. Integration tests
live under ``tests/integration`` behind the ``needs_orientdb`` marker.
"""

from __future__ import annotations

import logging
import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.graph.orientdb_config import OrientDBConfig
from pirn.connectors.graph.orientdb_pool import OrientDBPool

# ──────────────────────────────────────────────────────────────── fakes


class FakeOrientRecord:
    """Minimal fake of a pyorient ORecord."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.oRecordData = data


class FakeOrientClient:
    """Mirrors the pyorient client surface used by OrientDBPool."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.commands: list[str] = []
        self.queries: list[str] = []
        self._records = records or []
        self.db_closed = False

    def command(self, query: str) -> list[Any]:
        self.commands.append(query)
        return ["EXECUTE OK"]

    def query(self, query: str, limit: int) -> list[FakeOrientRecord]:
        self.queries.append(query)
        return [FakeOrientRecord(r) for r in self._records]

    def db_close(self) -> None:
        self.db_closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = OrientDBPool(client=FakeOrientClient())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            OrientDBPool()
    
    
    def test_config_with_empty_database_raises_value_error(self) -> None:
        cfg = OrientDBConfig(host="localhost", database="")
        with self.assertRaisesRegex(ValueError, "database must be non-empty"):
            OrientDBPool(config=cfg)
    
    
# ────────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_delegates_to_client_command(self) -> None:
        fake = FakeOrientClient()
        pool = OrientDBPool(client=fake)
        result = await pool.execute("INSERT INTO Person SET name = 'Alice'")
        assert "INSERT INTO Person SET name = 'Alice'" in fake.commands
        assert isinstance(result, str)

    async def test_fetch_all_returns_list_of_dicts(self) -> None:
        records = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        fake = FakeOrientClient(records=records)
        pool = OrientDBPool(client=fake)
        result = await pool.fetch_all("SELECT * FROM Person")
        assert result == records
        assert "SELECT * FROM Person" in fake.queries

    async def test_execute_many_runs_each_item(self) -> None:
        fake = FakeOrientClient()
        pool = OrientDBPool(client=fake)
        await pool.execute_many(
            "INSERT INTO Person SET name = 'Alice'",
            [None, None, None],
        )
        assert len(fake.commands) == 3

    async def test_acquire_returns_client(self) -> None:
        fake = FakeOrientClient()
        pool = OrientDBPool(client=fake)
        client = await pool.acquire()
        assert client is fake

    async def test_release_is_noop(self) -> None:
        fake = FakeOrientClient()
        pool = OrientDBPool(client=fake)
        client = await pool.acquire()
        await pool.release(client)
        assert not fake.db_closed


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_db_close(self) -> None:
        fake = FakeOrientClient()
        pool = OrientDBPool(client=fake)
        await pool.close()
        assert fake.db_closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = OrientDBPool(client=FakeOrientClient())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = OrientDBPool(config=OrientDBConfig(database="testdb"), client=FakeOrientClient())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = OrientDBPool(config=OrientDBConfig(database="testdb"), client=FakeOrientClient())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ──────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = OrientDBConfig(password="orient-secret")
        assert "orient-secret" not in repr(cfg)
        assert "<redacted>" in repr(cfg)

    def test_audit_dict_redacts_password(self) -> None:
        cfg = OrientDBConfig(password="orient-secret")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "orient-secret" not in str(d)

    def test_repr_shows_host_and_port(self) -> None:
        cfg = OrientDBConfig(host="orient.example.com", port=2424, database="mydb")
        text = repr(cfg)
        assert "orient.example.com" in text
        assert "2424" in text


# ────────────────────────────────────────────────────────────── log events


class TestLogEvents(unittest.IsolatedAsyncioTestCase):
    async def test_close_emits_debug_log(self) -> None:
        pool = OrientDBPool(client=FakeOrientClient())
        with self.assertLogs("pirn", level=logging.DEBUG) as cm:
            await pool.close()
        assert any("orientdb.close" in msg for msg in cm.output)
