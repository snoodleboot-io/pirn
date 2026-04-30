"""Mock-driver tests for the Postgres backend.

These tests use a fake asyncpg pool that records every query and
parameter binding, returning canned responses for fetches.  They
verify the backend's SQL/binding logic without needing a real
Postgres server.

Real-server tests are gated by ``@pytest.mark.needs_postgres`` and
live alongside these — see ``test_postgres_real.py`` (added when the
test infrastructure for real backends is built out; see
``docs/real-backend-testing-plan.md``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from pirn.backends.postgres.postgres_history import PostgresHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# -------------------------------------------------- fake asyncpg pool


class _FakeRow(dict):
    """asyncpg rows behave like dicts; this mimics the API surface we
    actually use (subscripting by column name)."""


class _FakeConn:
    """Fake asyncpg connection.

    Records every ``execute`` and ``fetch``/``fetchrow`` call so tests
    can assert which queries the backend issued.  ``set_canned`` lets a
    test seed the responses.
    """

    def __init__(self, recorder: _FakePool) -> None:
        self._recorder = recorder

    async def execute(self, query: str, *args: Any) -> str:
        self._recorder.executes.append((query, args))
        return "OK"

    async def executemany(self, query: str, args: list) -> None:
        self._recorder.executemany_calls.append((query, args))

    async def fetchrow(self, query: str, *args: Any) -> _FakeRow | None:
        self._recorder.fetches.append((query, args))
        for matcher, response in self._recorder.canned_rows:
            if matcher(query, args):
                return response
        return None

    async def fetch(self, query: str, *args: Any) -> list[_FakeRow]:
        self._recorder.fetches.append((query, args))
        for matcher, response in self._recorder.canned_lists:
            if matcher(query, args):
                return response
        return []

    @asynccontextmanager
    async def transaction(self):
        yield


class _FakePool:
    """Fake asyncpg pool.  Records all conn-level activity."""

    def __init__(self) -> None:
        self.executes: list[tuple[str, tuple]] = []
        self.executemany_calls: list[tuple[str, list]] = []
        self.fetches: list[tuple[str, tuple]] = []
        self.canned_rows: list[tuple[Any, Any]] = []
        self.canned_lists: list[tuple[Any, Any]] = []

    @asynccontextmanager
    async def acquire(self):
        yield _FakeConn(self)

    async def close(self) -> None:
        pass


# ---------------------------------------------------- helpers


@knot
async def _double(x: int) -> int:
    return x * 2


async def _make_run_result(value: int) -> Any:
    """Build a real RunResult by running a pipeline against an InMemory
    history, then return that result for use against the fake pool."""
    from pirn.backends.in_memory.in_memory_history import InMemoryHistory

    h = InMemoryHistory()
    with Tapestry(history=h) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    return await t.run(RunRequest(parameters={"x": value}))


# ---------------------------------------------------- tests


async def test_postgres_history_init_executes_ddl():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    await history._ensure_init()
    # First execute should be the DDL.
    assert pool.executes
    all_queries = " ".join(q for q, _ in pool.executes)
    assert "CREATE TABLE" in all_queries
    assert "runs" in all_queries
    assert "lineage" in all_queries


async def test_postgres_history_record_run_inserts_runs_row():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    result = await _make_run_result(5)
    await history.record_run(result)

    # Find the INSERT INTO runs.
    insert_runs = [(q, a) for q, a in pool.executes if "INSERT INTO runs" in q]
    assert len(insert_runs) == 1
    _, args = insert_runs[0]
    # First arg is run_id.
    assert args[0] == result.run_id


async def test_postgres_history_record_run_inserts_lineage_rows():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    result = await _make_run_result(5)
    await history.record_run(result)

    insert_lineage = [
        (q, rows) for q, rows in pool.executemany_calls if "INSERT INTO lineage VALUES" in q
    ]
    assert len(insert_lineage) == 1
    assert len(insert_lineage[0][1]) == len(result.lineage)


async def test_postgres_history_record_run_inserts_lineage_inputs():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    result = await _make_run_result(5)
    await history.record_run(result)

    insert_inputs = [
        (q, rows) for q, rows in pool.executemany_calls if "INSERT INTO lineage_inputs" in q
    ]
    expected = sum(len(rec.parent_input_hashes) for rec in result.lineage)
    # executemany is called once with all rows batched together
    assert len(insert_inputs) == 1
    assert len(insert_inputs[0][1]) == expected


async def test_postgres_history_get_run_uses_correct_query_and_binding():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    await history.get_run("some-run-id")
    # Find the SELECT against runs.
    fetches = [(q, a) for q, a in pool.fetches if "FROM runs" in q]
    assert len(fetches) == 1
    query, args = fetches[0]
    assert "WHERE run_id = $1" in query
    assert args == ("some-run-id",)


async def test_postgres_history_get_run_returns_none_when_missing():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    fetched = await history.get_run("missing")
    assert fetched is None


async def test_postgres_history_get_run_decodes_payload_when_present():
    pool = _FakePool()
    result = await _make_run_result(7)

    # Seed canned response for the get_run query.
    def matcher(query, args):
        return "FROM runs" in query and args == (result.run_id,)

    pool.canned_rows.append((matcher, _FakeRow(payload_json=result.model_dump_json())))
    history = PostgresHistory(pool=pool)
    fetched = await history.get_run(result.run_id)
    assert fetched is not None
    assert fetched.run_id == result.run_id
    assert fetched.outputs == result.outputs


async def test_postgres_history_query_by_output_hash_uses_correct_sql():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    await history.query_lineage_by_output_hash("sha256:test")
    fetches = [(q, a) for q, a in pool.fetches if "WHERE output_hash" in q]
    assert len(fetches) == 1
    _, args = fetches[0]
    assert args == ("sha256:test",)


async def test_postgres_history_query_by_input_hash_uses_join():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    await history.query_lineage_by_input_hash("sha256:test")
    fetches = [(q, a) for q, a in pool.fetches if "JOIN lineage_inputs" in q]
    assert len(fetches) == 1


async def test_postgres_history_query_by_knot_id_uses_correct_sql():
    pool = _FakePool()
    history = PostgresHistory(pool=pool)
    await history.query_lineage_by_knot_id("my_knot")
    fetches = [(q, a) for q, a in pool.fetches if "WHERE knot_id" in q]
    assert len(fetches) == 1
    _, args = fetches[0]
    assert args == ("my_knot",)
