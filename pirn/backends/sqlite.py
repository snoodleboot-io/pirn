"""SQLite backend.

Provides ``SQLiteStore`` (TapestryStore) and ``SQLiteHistory`` (RunHistory)
backed by a single SQLite database via ``aiosqlite``.  Suitable for
small-team / single-host deployments and as a durable local development
backend.

Knots are not directly serializable (they hold callable references), so
``SQLiteStore`` stores a *snapshot* of each knot — its id, class name,
config, parent ids — without trying to reconstruct the live knot.  The
live knot lives in the engine's working memory; the store captures
enough metadata to support cross-process queries about what the
tapestry looks like.

This is the right shape for production: the store never needs to
reconstruct a live knot, because the tapestry is rebuilt on each
process start from user code.  The store's job is to record what the
tapestry says and answer queries about it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pirn.backends import TapestrySnapshot
from pirn.core.lineage import KnotLineage

if TYPE_CHECKING:
    from pirn.core.knot import Knot


# ---------------------------------------------------------------- DDL

_SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS pirn_schema_version (
    component TEXT PRIMARY KEY,
    version INTEGER NOT NULL
);
"""

_STORE_SCHEMA_VERSION = 1
_HISTORY_SCHEMA_VERSION = 1

_STORE_DDL = """
CREATE TABLE IF NOT EXISTS knots (
    knot_id TEXT PRIMARY KEY,
    knot_class TEXT NOT NULL,
    config_json TEXT NOT NULL,
    parents_json TEXT NOT NULL,
    registered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knots_class ON knots(knot_class);
"""

_HISTORY_DDL = """
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


# ----------------------------------------------------------- Migration helper


def _apply_sqlite_migrations(conn: Any, component: str, target: int) -> None:
    """Advance the schema version for ``component`` from current to ``target``.

    Each step calls ``_migrate_{v}_to_{v+1}(conn)`` if it exists; right
    now there are no such functions because v1 is the initial schema.
    Add them here as the schema evolves.
    """
    row = conn.execute(
        "SELECT version FROM pirn_schema_version WHERE component = ?",
        (component,),
    ).fetchone()
    current = row[0] if row else 0
    for _v in range(current, target):
        pass  # _migrate_{_v}_to_{_v+1}(conn) goes here when needed
    conn.execute(
        "INSERT OR REPLACE INTO pirn_schema_version (component, version) VALUES (?, ?)",
        (component, target),
    )


# ----------------------------------------------------------- Store


class SQLiteStore:
    """``TapestryStore`` backed by SQLite.

    Provide either an existing ``sqlite3.Connection`` (for tests or
    shared-connection setups) or a file path; if a path is given the
    store opens its own connection lazily on first use.

    **Concurrency model — single writer:**
    SQLite serialises all writes through one connection.  This is safe
    and fast for all single-process use cases (knot registration writes
    are tiny, infrequent, and never on the hot path).

    *WAL mode* allows concurrent readers alongside the single writer.
    Enable it by passing a pre-configured connection::

        import sqlite3
        conn = sqlite3.connect("pirn.db")
        conn.execute("PRAGMA journal_mode=WAL")
        store = SQLiteStore(connection=conn)

    **Connection pooling is intentionally not provided** for this backend.
    SQLite's threading model means a single ``check_same_thread=False``
    connection shared across coroutines is safe (GIL-protected), and a
    pool would not improve write throughput — SQLite still serialises
    writers regardless.  If you need genuine write concurrency across
    processes or high-volume knot registration, switch to
    ``PostgresStore`` or ``ValKeyStore``.
    """

    def __init__(self, *, path: str = ":memory:", connection: Any = None) -> None:
        try:
            import sqlite3
        except ImportError as exc:  # pragma: no cover
            raise ImportError("SQLiteStore requires the standard library sqlite3 module") from exc

        self._path = path
        self._conn = connection or sqlite3.connect(path)
        # In-memory live cache — knots aren't serializable as live
        # objects, so we keep the originals here for `get()`.  The
        # database holds the snapshot for cross-process queries.
        self._live: dict[str, Knot] = {}
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._conn.executescript(_SCHEMA_VERSION_DDL + _STORE_DDL)
        _apply_sqlite_migrations(self._conn, "store", _STORE_SCHEMA_VERSION)
        self._conn.commit()
        self._initialized = True

    def register(self, knot: Knot) -> None:
        from datetime import UTC, datetime

        self._ensure_init()
        existing = self._live.get(knot.knot_id)
        if existing is not None and existing is not knot:
            raise ValueError(
                f"knot id {knot.knot_id!r} already registered with a different instance"
            )
        self._live[knot.knot_id] = knot

        config_json = knot.config.model_dump_json()
        parents_json = json.dumps({name: parent.knot_id for name, parent in knot.parents.items()})
        knot_class = f"{type(knot).__module__}.{type(knot).__qualname__}"
        now = datetime.now(UTC).isoformat()

        self._conn.execute(
            """INSERT OR REPLACE INTO knots
               (knot_id, knot_class, config_json, parents_json, registered_at)
               VALUES (?, ?, ?, ?, ?)""",
            (knot.knot_id, knot_class, config_json, parents_json, now),
        )
        self._conn.commit()

    def get(self, knot_id: str) -> Knot | None:
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        self._ensure_init()
        cursor = self._conn.execute("SELECT knot_id FROM knots ORDER BY registered_at")
        return TapestrySnapshot(knot_ids=[row[0] for row in cursor.fetchall()])

    def close(self) -> None:
        self._conn.close()


# ----------------------------------------------------------- History


class SQLiteHistory:
    """``RunHistory`` backed by SQLite.

    All methods are async to satisfy the protocol, but underneath we use
    blocking ``sqlite3`` — SQLite is fast enough for in-memory and
    single-host file-backed scenarios that an async wrapper adds no
    real concurrency benefit (writes are already serialised).

    **Connection pooling is intentionally not provided.**  Lineage writes
    are batched via ``executemany`` so a single connection handles
    thousands of runs per second without becoming a bottleneck.  If you
    need concurrent multi-process writes or OLAP queries over millions of
    lineage rows, use ``PostgresHistory`` or ``DuckDBHistory`` instead.

    Share a ``sqlite3.Connection`` between ``SQLiteStore`` and
    ``SQLiteHistory`` to keep everything in one file::

        import sqlite3
        conn = sqlite3.connect("pirn.db", check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        store   = SQLiteStore(connection=conn)
        history = SQLiteHistory(connection=conn)
    """

    def __init__(self, *, path: str = ":memory:", connection: Any = None) -> None:
        import sqlite3

        self._path = path
        self._conn = connection or sqlite3.connect(path)
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._conn.executescript(_SCHEMA_VERSION_DDL + _HISTORY_DDL)
        _apply_sqlite_migrations(self._conn, "history", _HISTORY_SCHEMA_VERSION)
        self._conn.commit()
        self._initialized = True

    async def record_run(self, result: Any) -> None:
        self._ensure_init()
        self._conn.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, succeeded, started_at, finished_at, dispatcher, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result.run_id,
                1 if result.succeeded else 0,
                result.started_at.isoformat(),
                result.finished_at.isoformat(),
                result.dispatcher,
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
                        rec.model_dump_json(),
                    )
                    for rec in result.lineage
                ],
            )
            input_rows = [
                (rec.run_id, rec.knot_id, input_name, input_hash)
                for rec in result.lineage
                for input_name, input_hash in rec.parent_input_hashes.items()
            ]
            if input_rows:
                self._conn.executemany(
                    """INSERT OR REPLACE INTO lineage_inputs
                       (run_id, knot_id, input_name, input_hash)
                       VALUES (?, ?, ?, ?)""",
                    input_rows,
                )
        self._conn.commit()

    async def get_run(self, run_id: str) -> Any:
        self._ensure_init()
        cursor = self._conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        from pirn.core.context import RunResult

        return RunResult.model_validate_json(row[0])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE output_hash = ?",
            (output_hash,),
        )
        return [KnotLineage.model_validate_json(row[0]) for row in cursor.fetchall()]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            """SELECT l.payload_json FROM lineage l
               JOIN lineage_inputs i
                 ON l.run_id = i.run_id AND l.knot_id = i.knot_id
               WHERE i.input_hash = ?""",
            (input_hash,),
        )
        return [KnotLineage.model_validate_json(row[0]) for row in cursor.fetchall()]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        self._ensure_init()
        cursor = self._conn.execute(
            "SELECT payload_json FROM lineage WHERE knot_id = ?", (knot_id,)
        )
        return [KnotLineage.model_validate_json(row[0]) for row in cursor.fetchall()]

    def close(self) -> None:
        self._conn.close()
