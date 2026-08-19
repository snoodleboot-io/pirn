from __future__ import annotations

import base64
import json
from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.backends.sqlite._migrations import apply_migrations
from pirn.core.knot_source import KnotSourceRecord
from pirn.core.lineage import KnotLineage


def _json_default(obj: Any) -> Any:
    """Fallback serializer: handle types pydantic model_dump leaves as Python objects."""
    if isinstance(obj, bytes):
        return {"__bytes_b64__": base64.b64encode(obj).decode()}
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses

        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _model_to_json(model: Any) -> str:
    """Serialize a pydantic model to JSON, handling bytes fields gracefully."""
    return json.dumps(model.model_dump(mode="python"), default=_json_default)


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

    **Transaction ownership.** Because that shared connection is the documented
    arrangement, every write here commits — or rolls back — exactly the
    transaction *its own statements* opened, and never touches one it found
    already open. This is the guarantee
    ``ColumnAwareSqlitePool.fetch_columns`` (PIR-801) and ``_SQLExecutor``
    (PIR-817) already make, and that ``SqlitePool`` takes up in PIR-819;
    ``sqlite3`` starts an implicit transaction for DML only, so comparing
    ``in_transaction`` before and after the statements identifies the owner
    precisely:

    * :meth:`record_run` and :meth:`record_knot_source` previously committed
      unconditionally, adopting a transaction opened by ``SQLiteStore`` on the
      shared connection or by the application itself — making someone else's
      half-written work durable and stealing their ability to roll it back
      (PIR-823);
    * :meth:`record_run` writes a run row plus two bulk inserts, so all three
      are wrapped together and a failure partway through rolls the whole thing
      back. Without that, the run row stayed in an open transaction with no
      matching lineage, and the next write on the connection committed that
      partial row. This matches what
      :meth:`~pirn.backends.postgres.postgres_history.PostgresHistory.record_run`
      already does with ``async with conn.transaction()``;
    * reads open no transaction and so issue no ``COMMIT``, which matters beyond
      tidiness: under ``journal_mode=DELETE`` a ``COMMIT`` must take the
      exclusive lock, so a concurrent reader would make a query that only read
      rows fail with ``database is locked``.

    One exception remains by design: :meth:`_ensure_init` runs the schema DDL
    through ``executescript``, which ``sqlite3`` documents as implicitly
    committing any pending transaction. Schema creation is one-time setup that
    must be durable for every later statement, so it is left unconditional —
    mirroring ``SqlitePool._open_connection``. Callers who hold a transaction
    across history calls should therefore let the history initialise first.
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
        CREATE TABLE IF NOT EXISTS knot_sources (
            source_hash TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            knot_class TEXT NOT NULL,
            pirn_version TEXT NOT NULL
        );
    """
    _schema_version = 4

    @staticmethod
    def __migrate_v2(conn: Any) -> None:
        """Add 7-W provenance columns to the runs table."""
        cols = (
            "actor TEXT",
            "trigger TEXT",
            "environment_json TEXT",
            "runtime_info_json TEXT",
        )
        for col in cols:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_actor ON runs(actor)")

    @staticmethod
    def __migrate_v3(conn: Any) -> None:
        """Add nesting columns for SubTapestry parent linking."""
        conn.execute("ALTER TABLE runs ADD COLUMN parent_run_id TEXT")
        conn.execute("ALTER TABLE runs ADD COLUMN parent_knot_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id)")

    @staticmethod
    def __migrate_v4(conn: Any) -> None:
        """Add knot_sources table for content-addressed source snapshots."""
        conn.execute(
            """CREATE TABLE IF NOT EXISTS knot_sources (
                source_hash TEXT PRIMARY KEY,
                source_text TEXT NOT NULL,
                knot_class TEXT NOT NULL,
                pirn_version TEXT NOT NULL
            )"""
        )

    def __init__(self, *, path: str = "pirn.db", connection: Any = None) -> None:
        """Initialise the history store.

        Args:
            path: File path for the SQLite database.  Defaults to
                ``"pirn.db"`` in the current working directory.  Pass
                ``":memory:"`` for a transient in-process store.  Ignored
                when ``connection`` is provided.
            connection: An existing ``sqlite3.Connection`` to reuse.  Useful
                for sharing a single file between ``SQLiteStore`` and
                ``SQLiteHistory``.
        """
        import sqlite3

        self._path = path
        self._conn = connection or sqlite3.connect(path)
        self._initialized = False

    def _ensure_init(self) -> None:
        """Create history tables and apply pending migrations on first call.

        Subsequent calls return immediately.
        """
        if self._initialized:
            return
        self._conn.executescript(self._schema_version_ddl + self._history_ddl)
        apply_migrations(
            self._conn,
            "history",
            self._schema_version,
            {2: self.__migrate_v2, 3: self.__migrate_v3, 4: self.__migrate_v4},
        )
        self._conn.commit()
        self._initialized = True

    async def record_run(self, result: Any) -> None:
        """Persist a run result and all associated lineage records.

        Inserts or replaces the run row, then bulk-inserts lineage rows and
        per-knot input hash rows.  All three statements share one transaction:
        it is committed only if this call opened it, and a failure partway
        through rolls back every row this call wrote, so a run is never left
        half-recorded.  See the class docstring.

        Args:
            result: A ``RunResult`` instance to persist.
        """
        self._ensure_init()
        in_transaction_on_entry = bool(self._conn.in_transaction)
        try:
            self._write_run(result)
        except BaseException:
            if self._opened_transaction(self._conn, in_transaction_on_entry):
                self._conn.rollback()
            raise
        if self._opened_transaction(self._conn, in_transaction_on_entry):
            self._conn.commit()

    def _write_run(self, result: Any) -> None:
        """Issue the run, lineage, and lineage-input statements.

        Args:
            result: A ``RunResult`` instance to persist.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, succeeded, started_at, finished_at, dispatcher,
                actor, trigger, environment_json, runtime_info_json,
                parent_run_id, parent_knot_id, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                result.parent_run_id,
                result.parent_knot_id,
                _model_to_json(result),
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
                        rec.run_id,
                        rec.knot_id,
                        rec.knot_class,
                        rec.knot_config_hash,
                        rec.output_hash,
                        rec.outcome,
                        rec.error_record_id,
                        rec.skip_reason,
                        rec.dispatcher,
                        rec.started_at.isoformat(),
                        rec.finished_at.isoformat(),
                        _model_to_json(rec),
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

    async def get_run(self, run_id: str) -> Any:
        """Fetch a single run by id.

        Args:
            run_id: UUID of the run to retrieve.

        Returns:
            A ``RunResult`` instance, or ``None`` if not found.
        """
        self._ensure_init()
        cursor = self._conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        from pirn.core.run_result import RunResult

        return RunResult.model_validate_json(row[0])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        """Return all lineage records whose output matched ``output_hash``.

        Args:
            output_hash: Content hash of the output to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE output_hash = ?", (output_hash,)
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        """Return all lineage records that consumed ``input_hash`` as an input.

        Joins ``lineage`` with ``lineage_inputs`` to locate all knots that
        depended on the given content hash.

        Args:
            input_hash: Content hash of the input to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        self._ensure_init()
        cursor = self._conn.execute(
            """SELECT l.payload_json FROM lineage l
               JOIN lineage_inputs i ON l.run_id = i.run_id AND l.knot_id = i.knot_id
               WHERE i.input_hash = ?""",
            (input_hash,),
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        """Return all lineage records for a specific knot across all runs.

        Args:
            knot_id: Identifier of the knot whose history is requested.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE knot_id = ?", (knot_id,)
        )
        return [KnotLineage.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        """Return all runs triggered by ``actor``.

        Args:
            actor: Actor string to filter by.

        Returns:
            List of ``RunResult`` objects, possibly empty.
        """
        self._ensure_init()
        from pirn.core.run_result import RunResult

        cursor = self._conn.execute("SELECT payload_json FROM runs WHERE actor = ?", (actor,))
        return [RunResult.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def children_of(self, run_id: str) -> list[Any]:
        """Return all runs whose ``parent_run_id`` matches ``run_id``.

        Args:
            run_id: UUID of the parent run.

        Returns:
            List of ``RunResult`` objects for all child runs, possibly empty.
        """
        self._ensure_init()
        from pirn.core.run_result import RunResult

        cursor = self._conn.execute(
            "SELECT payload_json FROM runs WHERE parent_run_id = ?", (run_id,)
        )
        return [RunResult.model_validate_json(r[0]) for r in cursor.fetchall()]

    async def record_knot_source(self, record: KnotSourceRecord) -> None:
        """Persist a knot source snapshot; no-op if the hash already exists.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.

        Args:
            record: The ``KnotSourceRecord`` to persist.
        """
        self._ensure_init()
        in_transaction_on_entry = bool(self._conn.in_transaction)
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO knot_sources
                   (source_hash, source_text, knot_class, pirn_version)
                   VALUES (?, ?, ?, ?)""",
                (record.source_hash, record.source_text, record.knot_class, record.pirn_version),
            )
        except BaseException:
            if self._opened_transaction(self._conn, in_transaction_on_entry):
                self._conn.rollback()
            raise
        if self._opened_transaction(self._conn, in_transaction_on_entry):
            self._conn.commit()

    async def get_knot_source(self, source_hash: str) -> KnotSourceRecord | None:
        """Fetch a knot source snapshot by content hash.

        Args:
            source_hash: SHA-256 hex digest as stored in ``KnotLineage.source_hash``.

        Returns:
            A ``KnotSourceRecord``, or ``None`` if not found.
        """
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT source_hash, source_text, knot_class, pirn_version "
            "FROM knot_sources WHERE source_hash = ?",
            (source_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return KnotSourceRecord(
            source_hash=row[0], source_text=row[1], knot_class=row[2], pirn_version=row[3]
        )

    @staticmethod
    def _opened_transaction(connection: Any, in_transaction_on_entry: bool) -> bool:
        """Whether the statements just run are what opened the now-open transaction.

        Args:
            connection: The ``sqlite3`` connection the statements ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                they ran.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one responsible
            for ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Only call this when the store owns the connection (i.e. opened from a
        file path).  Shared injected connections must be closed by the caller.
        """
        self._conn.close()
