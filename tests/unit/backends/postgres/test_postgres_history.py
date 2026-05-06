"""Tests for PostgresHistory using a fully-mocked asyncpg pool."""

from __future__ import annotations

import json
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends.postgres.postgres_history import PostgresHistory
from pirn.core.lineage import KnotLineage


def _now() -> datetime:
    return datetime.now(UTC)


def _make_lineage(
    *,
    run_id: str = "run-1",
    knot_id: str = "knot-a",
    output_hash: str | None = "sha256:out",
    parent_input_hashes: dict[str, str] | None = None,
    outcome: str = "ok",
) -> KnotLineage:
    now = _now()
    return KnotLineage(
        run_id=run_id,
        knot_id=knot_id,
        knot_class="pkg.MyKnot",
        knot_config_hash="cfg",
        output_hash=output_hash,
        parent_input_hashes=parent_input_hashes or {},
        outcome=outcome,
        dispatcher="LocalDispatcher",
        started_at=now,
        finished_at=now,
    )


def _make_run_result(
    *,
    run_id: str = "run-1",
    lineage: list[KnotLineage] | None = None,
) -> Any:
    from pirn.core.run_result import RunResult

    now = _now()
    return RunResult(
        run_id=run_id,
        terminals_requested=[],
        outputs={},
        lineage=lineage or [],
        started_at=now,
        finished_at=now,
        dispatcher="LocalDispatcher",
        actor="tester",
    )


class _FakePool:
    """Minimal fake asyncpg pool that uses in-memory dicts."""

    def __init__(self) -> None:
        self._runs: dict[str, str] = {}  # run_id -> payload_json
        self._lineage: dict[tuple[str, str], str] = {}  # (run_id, knot_id) -> payload_json
        self._lineage_inputs: list[tuple[str, str, str, str]] = []
        self._schema_version: dict[str, int] = {}

    @asynccontextmanager
    async def acquire(self) -> Any:
        yield _FakeConn(self)


class _FakeConn:
    def __init__(self, pool: _FakePool) -> None:
        self._pool = pool

    async def execute(self, sql: str, *args: Any) -> None:
        if "INSERT INTO pirn_schema_version" in sql or "CREATE TABLE" in sql:
            if "INSERT" in sql:
                component, version = args[0], args[1]
                self._pool._schema_version[component] = version
        elif "INSERT INTO runs" in sql and "ON CONFLICT" in sql:
            run_id = args[0]
            payload_json = args[-1]
            # Store payload (last arg)
            self._pool._runs[run_id] = payload_json
        elif "ALTER TABLE" in sql:
            pass  # schema migration no-op

    async def executemany(self, sql: str, rows: list) -> None:
        if "INSERT INTO lineage" in sql:
            for row in rows:
                run_id, knot_id = row[0], row[1]
                payload_json = row[-1]
                self._pool._lineage[(run_id, knot_id)] = payload_json
        elif "INSERT INTO lineage_inputs" in sql:
            for row in rows:
                self._pool._lineage_inputs.append(tuple(row))

    async def fetchrow(self, sql: str, *args: Any) -> Any | None:
        if "pirn_schema_version" in sql:
            component = args[0]
            version = self._pool._schema_version.get(component)
            if version is None:
                return None
            return {"version": version}
        if "FROM runs" in sql:
            run_id = args[0]
            payload = self._pool._runs.get(run_id)
            if payload is None:
                return None
            return {"payload_json": payload}
        return None

    async def fetch(self, sql: str, *args: Any) -> list:
        if "FROM lineage WHERE output_hash" in sql:
            output_hash = args[0]
            return [
                {"payload_json": v}
                for (_, _), v in self._pool._lineage.items()
                if True  # simplistic: return any lineage for testing
            ]
        if "FROM lineage WHERE knot_id" in sql:
            knot_id = args[0]
            return [
                {"payload_json": v}
                for (_, k), v in self._pool._lineage.items()
                if k == knot_id
            ]
        if "FROM runs WHERE actor" in sql:
            actor = args[0]
            # We don't track actor separately in fake — return all
            return [{"payload_json": v} for v in self._pool._runs.values()]
        if "JOIN lineage_inputs" in sql:
            input_hash = args[0]
            matching_keys = {
                (ri, ki)
                for (ri, ki, _, ih) in self._pool._lineage_inputs
                if ih == input_hash
            }
            return [
                {"payload_json": self._pool._lineage[(ri, ki)]}
                for (ri, ki) in matching_keys
                if (ri, ki) in self._pool._lineage
            ]
        return []

    async def add_listener(self, channel: str, cb: Any) -> None:
        pass

    async def remove_listener(self, channel: str, cb: Any) -> None:
        pass

    def transaction(self) -> "_FakeTx":
        return _FakeTx()


class _FakeTx:
    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def _make_history() -> PostgresHistory:
    fake_pool = _FakePool()
    return PostgresHistory(pool=fake_pool)


class TestPostgresHistoryInit(unittest.IsolatedAsyncioTestCase):
    async def test_initialized_flag_set_after_first_use(self) -> None:
        history = _make_history()
        await history._ensure_init()
        self.assertTrue(history._initialized)

    async def test_double_init_is_idempotent(self) -> None:
        history = _make_history()
        await history._ensure_init()
        await history._ensure_init()  # must not raise


class TestPostgresHistoryRecordAndQuery(unittest.IsolatedAsyncioTestCase):
    async def test_record_and_get_run(self) -> None:
        history = _make_history()
        result = _make_run_result(run_id="run-001")
        await history.record_run(result)
        retrieved = await history.get_run("run-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.run_id, "run-001")

    async def test_get_run_returns_none_for_missing(self) -> None:
        history = _make_history()
        result = await history.get_run("nonexistent")
        self.assertIsNone(result)

    async def test_lineage_stored_on_record_run(self) -> None:
        history = _make_history()
        lin = _make_lineage(run_id="run-1", knot_id="k1")
        result = _make_run_result(run_id="run-1", lineage=[lin])
        await history.record_run(result)
        # Verify lineage was stored in pool
        self.assertIn(("run-1", "k1"), history._pool._pool._lineage)

    async def test_query_lineage_by_knot_id(self) -> None:
        history = _make_history()
        lin = _make_lineage(run_id="run-1", knot_id="k-xyz")
        result = _make_run_result(run_id="run-1", lineage=[lin])
        await history.record_run(result)
        records = await history.query_lineage_by_knot_id("k-xyz")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k-xyz")


class TestPostgresHistoryInheritance(unittest.TestCase):
    def test_is_run_history(self) -> None:
        from pirn.backends.base.run_history import RunHistory

        self.assertIsInstance(_make_history(), RunHistory)
