"""DuckDB backend.

Provides ``DuckDBHistory`` — a ``RunHistory`` backed by DuckDB.  DuckDB
is an OLAP database: it's optimised for analytical queries over the
history (range scans, aggregations, joins across many runs).  Lineage
queries are exactly that workload.

DuckDB is *not* the right backend for the ``TapestryStore`` (which
needs single-row OLTP writes on every knot registration).  Use
``SQLiteStore`` or ``PostgresStore`` for that and pair it with
``DuckDBHistory`` for the lineage analytics.

Schema mirrors the SQLite history; the differences are in which
queries are fast (DuckDB's column-store wins on
``query_lineage_by_class`` style scans across many runs).
"""

from __future__ import annotations

from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.core.lineage import KnotLineage


class DuckDBHistory(RunHistory):
    """``RunHistory`` backed by DuckDB.

    Provide either an existing connection or a path; ``:memory:`` for
    transient analytics, a file path for durable history.
    """

    __ddl = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    succeeded BOOLEAN NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NOT NULL,
    dispatcher VARCHAR NOT NULL,
    actor VARCHAR,
    trigger VARCHAR,
    environment_json VARCHAR,
    runtime_info_json VARCHAR,
    payload_json VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS lineage (
    run_id VARCHAR NOT NULL,
    knot_id VARCHAR NOT NULL,
    knot_class VARCHAR NOT NULL,
    knot_config_hash VARCHAR NOT NULL,
    output_hash VARCHAR,
    outcome VARCHAR NOT NULL,
    error_record_id VARCHAR,
    skip_reason VARCHAR,
    dispatcher VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NOT NULL,
    payload_json VARCHAR NOT NULL,
    PRIMARY KEY (run_id, knot_id)
);
CREATE TABLE IF NOT EXISTS lineage_inputs (
    run_id VARCHAR NOT NULL,
    knot_id VARCHAR NOT NULL,
    input_name VARCHAR NOT NULL,
    input_hash VARCHAR NOT NULL,
    PRIMARY KEY (run_id, knot_id, input_name)
);
"""

    def __init__(self, *, path: str = ":memory:", connection: Any = None) -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise ImportError(
                "DuckDBHistory requires the duckdb package; install via `pip install pirn[duckdb]`"
            ) from exc

        self._path = path
        self._conn = connection or duckdb.connect(path)  # type: ignore[attr-defined]
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._conn.execute(DuckDBHistory.__ddl)
        self._initialized = True

    async def record_run(self, result: Any) -> None:
        import json
        self._ensure_init()
        self._conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.run_id,
                result.succeeded,
                result.started_at,
                result.finished_at,
                result.dispatcher,
                result.actor,
                result.trigger,
                json.dumps(result.environment),
                json.dumps(result.runtime_info),
                result.model_dump_json(),
            ),
        )
        for rec in result.lineage:
            self._conn.execute(
                "INSERT OR REPLACE INTO lineage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.run_id,
                    rec.knot_id,
                    rec.knot_class,
                    rec.knot_config_hash,
                    rec.output_hash,
                    rec.outcome,
                    rec.error_record_id,
                    rec.skip_reason,
                    rec.dispatcher,
                    rec.started_at,
                    rec.finished_at,
                    rec.model_dump_json(),
                ),
            )
            for input_name, input_hash in rec.parent_input_hashes.items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO lineage_inputs VALUES (?, ?, ?, ?)",
                    (rec.run_id, rec.knot_id, input_name, input_hash),
                )

    async def get_run(self, run_id: str) -> Any:
        self._ensure_init()
        rows = self._conn.execute(
            "SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)
        ).fetchall()
        if not rows:
            return None
        from pirn.core.run_result import RunResult

        return RunResult.model_validate_json(rows[0][0])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        rows = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE output_hash = ?",
            (output_hash,),
        ).fetchall()
        return [KnotLineage.model_validate_json(row[0]) for row in rows]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        rows = self._conn.execute(
            """SELECT l.payload_json FROM lineage l
               JOIN lineage_inputs i
                 ON l.run_id = i.run_id AND l.knot_id = i.knot_id
               WHERE i.input_hash = ?""",
            (input_hash,),
        ).fetchall()
        return [KnotLineage.model_validate_json(row[0]) for row in rows]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        self._ensure_init()
        rows = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE knot_id = ?", (knot_id,)
        ).fetchall()
        return [KnotLineage.model_validate_json(row[0]) for row in rows]

    # --------------- DuckDB-specific analytical methods -----------------

    async def query_lineage_by_class(self, knot_class: str) -> list[KnotLineage]:
        """All lineage records for a given knot class across all runs.

        Specific to DuckDB because it's an analytical query that benefits
        from columnar storage.  Other RunHistory backends may not
        implement this; check ``hasattr`` before calling, or rely on
        ``query_lineage_by_knot_id`` for portable access.
        """
        self._ensure_init()
        rows = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE knot_class = ?",
            (knot_class,),
        ).fetchall()
        return [KnotLineage.model_validate_json(row[0]) for row in rows]

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        self._ensure_init()
        from pirn.core.run_result import RunResult
        rows = self._conn.execute(
            "SELECT payload_json FROM runs WHERE actor = ?", (actor,)
        ).fetchall()
        return [RunResult.model_validate_json(row[0]) for row in rows]

    async def run_count(self) -> int:
        """Total number of recorded runs."""
        self._ensure_init()
        rows = self._conn.execute("SELECT COUNT(*) FROM runs").fetchall()
        return int(rows[0][0])

    def close(self) -> None:
        self._conn.close()
