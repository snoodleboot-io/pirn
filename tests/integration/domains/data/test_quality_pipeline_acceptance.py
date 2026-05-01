"""ATDD acceptance test: extract → quality assessment → Gate → load.

Demonstrates the canonical pirn pattern for the data-domain quality
knots:

1. A source produces a :class:`DataBatch`.
2. ``SchemaValidator`` and ``RowCountGate`` assess the batch and emit
   :class:`QualityReport` outputs (always — they don't raise).
3. A :class:`pirn.nodes.gate.gate.Gate` keyed on
   ``QualityReport.passed`` halts the pipeline when any check failed,
   producing a :class:`Skipped` instead of a passing batch.
4. A downstream knot (the "load" stage) only runs when every gate
   passes.

The "happy path" should run all knots and reach the load. The "blocked"
path (a batch that fails the schema check) should produce a Skipped
load — proving the gate halts as designed.
"""

from __future__ import annotations

import json

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.quality.row_count_gate import RowCountGate
from pirn.domains.data.quality.schema_validator import SchemaValidator
from pirn.domains.data.quality_report import QualityReport
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry


_USERS_SCHEMA = DataSchema(
    columns={"id": int, "name": str, "region": str},
    primary_keys=("id",),
)


@knot
async def emit_valid_users() -> DataBatch:
    rows = (
        {"id": 1, "name": "alice", "region": "EU"},
        {"id": 2, "name": "bob",   "region": "US"},
        {"id": 3, "name": "priya", "region": "IN"},
    )
    return DataBatch(rows=rows, schema=_USERS_SCHEMA)


@knot
async def emit_invalid_users() -> DataBatch:
    # 'region' missing on the second row — the schema validator should fail it.
    rows = (
        {"id": 1, "name": "alice", "region": "EU"},
        {"id": 2, "name": "bob"},
    )
    return DataBatch(rows=rows, schema=_USERS_SCHEMA)


@knot
async def project_for_load(batch: DataBatch) -> list[tuple[int, str, str]]:
    """Convert :class:`DataBatch` rows to the parameter tuples the sink expects."""
    return [(int(r["id"]), str(r["name"]), str(r["region"])) for r in batch.rows]


def _build_pipeline(
    *,
    pool: SqlitePool,
    invalid: bool,
) -> Tapestry:
    extract_knot = emit_invalid_users if invalid else emit_valid_users

    with Tapestry() as t:
        batch = extract_knot(_config=KnotConfig(id="extract"))

        schema_report = SchemaValidator(
            batch=batch,
            schema=_USERS_SCHEMA,
            _config=KnotConfig(id="schema"),
        )
        rowcount_report = RowCountGate(
            batch=batch,
            min_rows=1,
            max_rows=10_000,
            _config=KnotConfig(id="rowcount"),
        )

        # Two halt points, one per quality assessment.
        schema_ok = Gate(
            input=schema_report,
            predicate=lambda r: r.passed,
            _config=KnotConfig(id="schema_ok"),
        )
        rowcount_ok = Gate(
            input=rowcount_report,
            predicate=lambda r: r.passed,
            _config=KnotConfig(id="rowcount_ok"),
        )

        # The load runs only when both gates pass — reference both as
        # implicit dependencies through the parent dict so the engine
        # waits for them before invoking project_for_load.
        rows = project_for_load(
            batch=batch,
            _config=KnotConfig(id="project"),
        )
        DatabaseExecuteSink(
            pool=pool,
            query="INSERT INTO users (id, name, region) VALUES (?, ?, ?)",
            rows=rows,
            schema_ok=schema_ok,        # implicit dep
            rowcount_ok=rowcount_ok,    # implicit dep
            _config=KnotConfig(id="load"),
        )
    return t


@pytest.mark.asyncio
async def test_happy_path_runs_load_with_all_quality_gates_passing() -> None:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )

        t = _build_pipeline(pool=pool, invalid=False)
        result = await t.run(RunRequest())

        assert result.succeeded
        # All quality reports passed.
        schema_report: QualityReport = result.outputs["schema"]
        rowcount_report: QualityReport = result.outputs["rowcount"]
        assert schema_report.passed is True
        assert rowcount_report.passed is True

        # And the load actually wrote the rows.
        loaded = await pool.fetch_all(
            "SELECT id, name, region FROM users ORDER BY id"
        )
        assert loaded == [
            (1, "alice", "EU"),
            (2, "bob", "US"),
            (3, "priya", "IN"),
        ]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_invalid_batch_halts_load_via_gate() -> None:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )

        t = _build_pipeline(pool=pool, invalid=True)
        result = await t.run(RunRequest())

        # The schema check should have failed; the gate should have closed;
        # the load should be Skipped.
        schema_report: QualityReport = result.outputs["schema"]
        assert schema_report.passed is False

        outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}
        assert outcomes["schema"] == "ok"          # the assessment ran
        assert outcomes["schema_ok"] == "skipped"  # the gate closed
        assert outcomes["load"] == "skipped"       # the sink never executed

        # And the database was never touched.
        loaded = await pool.fetch_all("SELECT COUNT(*) FROM users")
        assert loaded == [(0,)]
    finally:
        await pool.close()
