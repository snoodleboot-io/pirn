"""PostgreSQL backend.

Provides ``PostgresStore`` and ``PostgresHistory`` over an ``asyncpg``
connection pool.  Pair them when you want a single durable database for
both definitions and lineage.

Construction takes either an existing pool (for tests / shared
connections) or a DSN.  When a DSN is provided the pool is created
lazily on first use; remember to call ``close()`` when done.

Schema notes
------------
* ``knots`` mirrors the SQLite store schema with PostgreSQL types.
* ``runs`` and ``lineage`` use ``JSONB`` for the payload columns so
  PostgreSQL's GIN indexing can be applied later if needed.
* The lineage tables use ``ON CONFLICT DO UPDATE`` instead of
  SQLite's ``INSERT OR REPLACE``.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
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

# Current schema version for each component.  Bump when adding migrations.
_STORE_SCHEMA_VERSION = 1
_HISTORY_SCHEMA_VERSION = 1

_STORE_DDL = """
CREATE TABLE IF NOT EXISTS knots (
    knot_id TEXT PRIMARY KEY,
    knot_class TEXT NOT NULL,
    config_json JSONB NOT NULL,
    parents_json JSONB NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_knots_class ON knots(knot_class);
"""

_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    succeeded BOOLEAN NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    dispatcher TEXT NOT NULL,
    payload_json JSONB NOT NULL
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
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    payload_json JSONB NOT NULL,
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
    PRIMARY KEY (run_id, knot_id, input_name)
);
CREATE INDEX IF NOT EXISTS idx_lineage_inputs_hash ON lineage_inputs(input_hash);
"""


# ------------------------------------------------------------- DSN sanitizer


def _sanitize_dsn(dsn: str) -> str:
    """Replace credentials in a DSN with <redacted> for safe logging/display."""
    return re.sub(r'(://)[^@]+(@)', r'\1<redacted>\2', dsn)


# ------------------------------------------------------------- Pool helper


class _LazyPool:
    """Wraps either an injected pool (test / sharing) or a DSN string."""

    def __init__(self, pool: Any = None, dsn: str | None = None) -> None:
        if pool is None and dsn is None:
            raise TypeError("provide either pool= or dsn=")
        self._pool = pool
        # Store DSN via closure — keeps it off the instance dict so it does
        # not appear in asyncpg traceback frames.
        _dsn = dsn
        self._get_dsn: Callable[[], str | None] = lambda: _dsn
        self._dsn_display = _sanitize_dsn(dsn) if dsn else None

    async def get(self) -> Any:
        if self._pool is None:
            try:
                import asyncpg
            except ImportError as exc:
                raise ImportError(
                    "PostgresStore/PostgresHistory require asyncpg; install "
                    "via `pip install pirn[postgres]`"
                ) from exc
            dsn = self._get_dsn()
            try:
                self._pool = await asyncpg.create_pool(dsn)
            except Exception as exc:
                # Re-raise with sanitized message so the password never appears
                # in ExceptionRecord.traceback_text.
                safe_msg = _sanitize_dsn(str(exc))
                raise type(exc)(safe_msg) from None
        return self._pool

    async def close(self) -> None:
        if self._pool is not None and self._get_dsn() is not None:
            # Only close pools we created ourselves.
            await self._pool.close()
            self._pool = None


# ----------------------------------------------------------- Store


class PostgresStore:
    """``TapestryStore`` backed by PostgreSQL via asyncpg.

    Implements the optional ``SubscribableStore`` protocol via Postgres
    LISTEN/NOTIFY: ``aregister`` sends ``NOTIFY pirn_knots, <knot_id>``
    after each INSERT, and ``subscribe`` spawns a background task that
    holds a dedicated connection in LISTEN mode and dispatches to
    registered callbacks whenever a notification arrives.

    Note: the NOTIFY signal is same-process only in this implementation.
    The callback receives the live ``Knot`` from the in-process cache
    (``self._live``); cross-process extension would require deserializing
    the knot from the database row, which is not yet supported.

    For sync registration use ``register``; for async-native use
    ``aregister``.
    """

    def __init__(self, *, pool: Any = None, dsn: str | None = None) -> None:
        self._pool = _LazyPool(pool=pool, dsn=dsn)
        self._live: dict[str, Knot] = {}
        self._initialized = False
        self._init_lock: asyncio.Lock = asyncio.Lock()
        self._subscribers: dict[int, Callable[[Any], None]] = {}
        self._next_token: int = 0
        self._listener_task: asyncio.Task[None] | None = None

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            pool = await self._pool.get()
            async with pool.acquire() as conn:
                await conn.execute(_SCHEMA_VERSION_DDL)
                await conn.execute(_STORE_DDL)
                await self._apply_migrations(conn, "store", _STORE_SCHEMA_VERSION)
            self._initialized = True

    @staticmethod
    async def _apply_migrations(conn: Any, component: str, target: int) -> None:
        row = await conn.fetchrow(
            "SELECT version FROM pirn_schema_version WHERE component = $1",
            component,
        )
        current = row["version"] if row else 0
        for _v in range(current, target):
            pass  # _migrate_{_v}_to_{_v+1}(conn) goes here when needed
        await conn.execute(
            """INSERT INTO pirn_schema_version (component, version)
               VALUES ($1, $2)
               ON CONFLICT (component) DO UPDATE SET version = EXCLUDED.version""",
            component,
            target,
        )

    async def aregister(self, knot: Knot) -> None:
        import json

        existing = self._live.get(knot.knot_id)
        if existing is not None and existing is not knot:
            raise ValueError(
                f"knot id {knot.knot_id!r} already registered with a different instance"
            )
        self._live[knot.knot_id] = knot

        await self._ensure_init()
        config_json = knot.config.model_dump_json()
        parents_json = json.dumps({name: parent.knot_id for name, parent in knot.parents.items()})
        knot_class = f"{type(knot).__module__}.{type(knot).__qualname__}"

        pool = await self._pool.get()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO knots
                   (knot_id, knot_class, config_json, parents_json)
                   VALUES ($1, $2, $3::jsonb, $4::jsonb)
                   ON CONFLICT (knot_id) DO UPDATE SET
                     knot_class = EXCLUDED.knot_class,
                     config_json = EXCLUDED.config_json,
                     parents_json = EXCLUDED.parents_json,
                     registered_at = NOW()""",
                knot.knot_id,
                knot_class,
                config_json,
                parents_json,
            )
            # Signal any in-process subscribers.  The payload is the knot_id;
            # subscribers look up the live instance from self._live.
            if self._subscribers:
                await conn.execute("SELECT pg_notify('pirn_knots', $1)", knot.knot_id)

    def register(self, knot: Knot) -> None:
        """Synchronous wrapper for protocol conformance.

        Schedules the async write on the running loop if there is one,
        else uses ``asyncio.run`` directly.  This is convenience for
        construction-time use inside a ``with Tapestry()`` block; for
        high-throughput registration call ``aregister`` directly.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            asyncio.run(self.aregister(knot))
        else:
            # We're inside a running loop; spawn a task and wait.  Since
            # the caller is sync, we have to drain the future.
            future = asyncio.ensure_future(self.aregister(knot))
            # Note: this only works if the running loop is *this thread's*
            # loop AND the caller releases control to it.  In a normal
            # `with Tapestry()` block at top level this is fine because
            # construction happens before `await t.run(...)`.  If a knot
            # is constructed mid-run, use aregister explicitly.
            self._live[knot.knot_id] = knot  # cached eagerly
            # Don't await here — the future will resolve when the loop
            # next runs.  This is the same hand-off behavior as
            # InMemoryStore (which doesn't need awaiting at all).
            del future

    def get(self, knot_id: str) -> Knot | None:
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        return TapestrySnapshot(knot_ids=list(self._live.keys()))

    def subscribe(self, callback: Callable[[Any], None]) -> object:
        """Register a callback fired for each newly registered knot.

        Returns a token; pass it to ``unsubscribe`` to remove the
        callback.  Starts the background LISTEN task on first subscriber.
        """
        token = self._next_token
        self._next_token += 1
        self._subscribers[token] = callback
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.ensure_future(self._listen_loop())
        return token

    def unsubscribe(self, token: object) -> None:
        self._subscribers.pop(token, None)  # type: ignore[arg-type]
        if not self._subscribers and self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None

    async def _listen_loop(self) -> None:
        """Hold a dedicated connection in LISTEN mode; dispatch to callbacks.

        asyncpg delivers NOTIFY payloads via add_listener, not cursor
        iteration.  We hold the connection open while subscribers exist.
        """
        pool = await self._pool.get()

        def _on_notify(conn: Any, pid: int, channel: str, payload: str) -> None:
            knot = self._live.get(payload)
            if knot is None:
                return
            for cb in list(self._subscribers.values()):
                try:
                    cb(knot)
                except Exception:
                    pass

        async with pool.acquire() as conn:
            await conn.add_listener("pirn_knots", _on_notify)
            try:
                while self._subscribers:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                pass
            finally:
                await conn.remove_listener("pirn_knots", _on_notify)

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None
        await self._pool.close()


# ----------------------------------------------------------- History


class PostgresHistory:
    """``RunHistory`` backed by PostgreSQL via asyncpg."""

    def __init__(self, *, pool: Any = None, dsn: str | None = None) -> None:
        self._pool = _LazyPool(pool=pool, dsn=dsn)
        self._initialized = False
        self._init_lock: asyncio.Lock = asyncio.Lock()

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            pool = await self._pool.get()
            async with pool.acquire() as conn:
                await conn.execute(_SCHEMA_VERSION_DDL)
                await conn.execute(_HISTORY_DDL)
                await PostgresStore._apply_migrations(conn, "history", _HISTORY_SCHEMA_VERSION)
            self._initialized = True

    async def record_run(self, result: Any) -> None:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO runs
                       (run_id, succeeded, started_at, finished_at, dispatcher, payload_json)
                       VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                       ON CONFLICT (run_id) DO UPDATE SET
                         succeeded = EXCLUDED.succeeded,
                         started_at = EXCLUDED.started_at,
                         finished_at = EXCLUDED.finished_at,
                         dispatcher = EXCLUDED.dispatcher,
                         payload_json = EXCLUDED.payload_json""",
                    result.run_id,
                    result.succeeded,
                    result.started_at,
                    result.finished_at,
                    result.dispatcher,
                    result.model_dump_json(),
                )
                if result.lineage:
                    await conn.executemany(
                        """INSERT INTO lineage VALUES
                           ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
                           ON CONFLICT (run_id, knot_id) DO UPDATE SET
                             output_hash = EXCLUDED.output_hash,
                             outcome = EXCLUDED.outcome,
                             error_record_id = EXCLUDED.error_record_id,
                             skip_reason = EXCLUDED.skip_reason,
                             payload_json = EXCLUDED.payload_json""",
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
                                rec.started_at,
                                rec.finished_at,
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
                        await conn.executemany(
                            """INSERT INTO lineage_inputs VALUES ($1, $2, $3, $4)
                               ON CONFLICT (run_id, knot_id, input_name) DO UPDATE SET
                                 input_hash = EXCLUDED.input_hash""",
                            input_rows,
                        )

    async def get_run(self, run_id: str) -> Any:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT payload_json FROM runs WHERE run_id = $1", run_id)
        if row is None:
            return None
        from pirn.core.context import RunResult

        return RunResult.model_validate_json(row["payload_json"])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload_json FROM lineage WHERE output_hash = $1",
                output_hash,
            )
        return [KnotLineage.model_validate_json(row["payload_json"]) for row in rows]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT l.payload_json FROM lineage l
                   JOIN lineage_inputs i
                     ON l.run_id = i.run_id AND l.knot_id = i.knot_id
                   WHERE i.input_hash = $1""",
                input_hash,
            )
        return [KnotLineage.model_validate_json(row["payload_json"]) for row in rows]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT payload_json FROM lineage WHERE knot_id = $1", knot_id)
        return [KnotLineage.model_validate_json(row["payload_json"]) for row in rows]

    async def close(self) -> None:
        await self._pool.close()
