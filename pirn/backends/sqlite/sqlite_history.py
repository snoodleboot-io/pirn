from __future__ import annotations

import json
from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.backends.sqlite._migrations import apply_migrations
from pirn.core.lineage import KnotLineage


class SQLiteHistory(RunHistory):
    """RunHistory backed by SQLite.

    Persists to ``pirn.db`` in the current working directory by default.
    Pass ``path=":memory:"`` explicitly for a transient in-process store.

    All methods are async to satisfy the interface but use blocking
    sqlite3 underneath — SQLite is fast enough for single-host scenarios
    that an async wrapper adds no real concurrency benefit.

    Share a sqlite3.Connection between SQLiteStore and SQLiteHistory to
    keep everything in one file::

        import sqlite3
        conn = sqlite3.connect("pirn.db", check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        store   = SQLiteStore(connection=conn)
        history = SQLiteHistory(connection=conn)
    """

    _schema_version_ddl = """
        CREATE TABLE IF NOT EXISTS pirn_schema_version (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL
        );
    """
    _history_ddl = """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            succeeded INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            dispatcher TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lineage (
            run_id TEXT NOT NULL,
            knot_id TEXT NOT NULL,
            knot_class TEXT NOT NULL,
            knot_config_hash TEXT NOT NULL,
            output_hash TEXT,
            outcome TEXT NOT NULL,
            error_record_id TEXT,
            skip_reason TEXT,
            dispatcher TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, knot_id)
        );
        CREATE INDEX IF NOT EXISTS idx_lineage_output_hash ON lineage(output_hash);
        CREATE INDEX IF NOT EXISTS idx_lineage_knot_id ON lineage(knot_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_class ON lineage(knot_class);
        CREATE TABLE IF NOT EXISTS lineage_inputs (
            run_id TEXT NOT NULL,
            knot_id TEXT NOT NULL,
            input_name TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            PRIMARY KEY (run_id, knot_id, input_name),
            FOREIGN KEY (run_id, knot_id) REFERENCES lineage(run_id, knot_id)
        );
        CREATE INDEX IF NOT EXISTS idx_lineage_inputs_hash ON lineage_inputs(input_hash);
    """
    _schema_version = 2

    @staticmethod
    def __migrate_v2(conn: Any) -> None:
        """Add 7-W provenance columns to the runs table."""
        for col in ("actor TEXT", "trigger TEXT", "environment_json TEXT", "runtime_info_json TEXT"):
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_actor ON runs(actor)")

    def __init__(self, *, path: str = "pirn.db", connection: Any = None) -> None:
        import sqlite3
        self._path = path
        self._conn = connection or sqlite3.connect(path)
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._conn.executescript(self._schema_version_ddl + self._history_ddl)
        apply_migrations(
            self._conn, "history", self._schema_version,
            {2: self.__migrate_v2},
        )
        self._conn.commit()
        self._initialized = True

    async def record_run(self, result: Any) -> None:
        self._ensure_init()
        self._conn.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, succeeded, started_at, finished_at, dispatcher,
                actor, trigger, environment_json, runtime_info_json, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.run_id,
                1 if result.succeeded else 0,
                result.started_at.isoformat(),
                result.finished_at.isoformat(),
                result.dispatcher,
                result.actor,
                result.trigger,
                json.dumps(result.environment),
                json.dumps(result.runtime_info),
                result.model_dump_json(),
            ),
        )
        if result.lineage:
            self._conn.executemany(
                """INSERT OR REPLACE INTO lineage
                   (run_id, knot_id, knot_class, knot_config_hash,
                    output_hash, outcome, error_record_id, skip_reason,
                    dispatcher, started_at, finished_at, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        rec.run_id, rec.knot_id, rec.knot_class, rec.knot_config_hash,
                        rec.output_hash, rec.outcome, rec.error_record_id, rec.skip_reason,
                        rec.dispatcher, rec.started_at.isoformat(),
                        rec.finished_at.isoformat(), rec.model_dump_json(),
                    )
                    for rec in result.lineage
                ],
            )
            input_rows = [
                (rec.run_id, rec.knot_id, name, h)
                for rec in result.lineage
                for name, h in rec.parent_input_hashes.items()
            ]
            if input_rows:
                self._conn.executemany(
                    """INSERT OR REPLACE INTO lineage_inputs
                       (run_id, knot_id, input_name, input_hash) VALUES (?, ?, ?, ?)""",
                    input_rows,
                )
        self._conn.commit()

    async def get_run(self, run_id: str) -> Any:
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        from pirn.core.run_result import RunResult
        return RunResult.model_validate_json(row[0])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE output_hash = ?", (output_hash,)
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            """SELECT l.payload_json FROM lineage l
               JOIN lineage_inputs i ON l.run_id = i.run_id AND l.knot_id = i.knot_id
               WHERE i.input_hash = ?""",
            (input_hash,),
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE knot_id = ?", (knot_id,)
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        self._ensure_init()
        from pirn.core.run_result import RunResult
        cursor = self._conn.execute(
            "SELECT payload_json FROM runs WHERE actor = ?", (actor,)
        )
        return [RunResult.model_validate_json(r[0]) for r in cursor.fetchall()]

    def close(self) -> None:
        self._conn.close()
