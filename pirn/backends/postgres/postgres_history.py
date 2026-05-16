from __future__ import annotations

import asyncio
from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.backends.postgres._lazy_pool import _LazyPool
from pirn.core.lineage import KnotLineage


class PostgresHistory(RunHistory):
    """RunHistory backed by PostgreSQL via asyncpg."""

    _schema_version_ddl = """
        CREATE TABLE IF NOT EXISTS pirn_schema_version (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL
        );
    """
    _history_ddl = """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            succeeded BOOLEAN NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ NOT NULL,
            dispatcher TEXT NOT NULL,
            actor TEXT,
            trigger TEXT,
            environment_json TEXT,
            runtime_info_json TEXT,
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
    _schema_version = 2

    def __init__(self, *, pool: Any = None, dsn: str | None = None) -> None:
        """Initialise the history store.

        Args:
            pool: An existing ``asyncpg`` connection pool to reuse.
            dsn: PostgreSQL connection string used to create a pool lazily on
                first use.  Mutually exclusive with ``pool``.

        Raises:
            TypeError: If neither ``pool`` nor ``dsn`` is provided.
        """
        self._pool = _LazyPool(pool=pool, dsn=dsn)
        self._initialized = False
        self._init_lock: asyncio.Lock = asyncio.Lock()

    async def _ensure_init(self) -> None:
        """Create history tables and apply pending migrations on first call.

        Uses a double-checked lock so concurrent callers don't race to
        create the tables.
        """
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            pool = await self._pool.get()
            async with pool.acquire() as conn:
                await conn.execute(self._schema_version_ddl)
                await conn.execute(self._history_ddl)
                await self._apply_migrations(conn)
            self._initialized = True

    async def _apply_migrations(self, conn: Any) -> None:
        """Apply any pending schema migrations within an open connection.

        Args:
            conn: An open ``asyncpg`` connection.
        """
        row = await conn.fetchrow(
            "SELECT version FROM pirn_schema_version WHERE component = $1", "history"
        )
        current = row["version"] if row else 0
        for v in range(current, self._schema_version):
            if v + 1 == 2:
                await self.__migrate_v2(conn)
        await conn.execute(
            """INSERT INTO pirn_schema_version (component, version)
               VALUES ($1, $2)
               ON CONFLICT (component) DO UPDATE SET version = EXCLUDED.version""",
            "history",
            self._schema_version,
        )

    @staticmethod
    async def __migrate_v2(conn: Any) -> None:
        """Add 7-W provenance columns to the runs table."""
        cols = ("actor TEXT", "trigger TEXT", "environment_json TEXT", "runtime_info_json TEXT")
        for col in cols:
            await conn.execute(f"ALTER TABLE runs ADD COLUMN IF NOT EXISTS {col}")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_actor ON runs(actor)")

    async def record_run(self, result: Any) -> None:
        """Persist a run result and all associated lineage records.

        All writes execute inside a single transaction; the run row and
        every lineage/input row are committed atomically.

        Args:
            result: A ``RunResult`` instance to persist.
        """
        import json

        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO runs
                       (run_id, succeeded, started_at, finished_at, dispatcher,
                        actor, trigger, environment_json, runtime_info_json, payload_json)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                       ON CONFLICT (run_id) DO UPDATE SET
                         succeeded = EXCLUDED.succeeded,
                         started_at = EXCLUDED.started_at,
                         finished_at = EXCLUDED.finished_at,
                         dispatcher = EXCLUDED.dispatcher,
                         actor = EXCLUDED.actor,
                         trigger = EXCLUDED.trigger,
                         environment_json = EXCLUDED.environment_json,
                         runtime_info_json = EXCLUDED.runtime_info_json,
                         payload_json = EXCLUDED.payload_json""",
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
                )
                if result.lineage:
                    await conn.executemany(
                        """INSERT INTO lineage VALUES
                           ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
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
                        (rec.run_id, rec.knot_id, name, h)
                        for rec in result.lineage
                        for name, h in rec.parent_input_hashes.items()
                    ]
                    if input_rows:
                        await conn.executemany(
                            """INSERT INTO lineage_inputs VALUES ($1,$2,$3,$4)
                               ON CONFLICT (run_id, knot_id, input_name) DO UPDATE SET
                                 input_hash = EXCLUDED.input_hash""",
                            input_rows,
                        )

    async def get_run(self, run_id: str) -> Any:
        """Fetch a single run by id.

        Args:
            run_id: UUID of the run to retrieve.

        Returns:
            A ``RunResult`` instance, or ``None`` if not found.
        """
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT payload_json FROM runs WHERE run_id = $1", run_id)
        if row is None:
            return None
        from pirn.core.run_result import RunResult

        return RunResult.model_validate_json(row["payload_json"])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        """Return all lineage records whose output matched ``output_hash``.

        Args:
            output_hash: Content hash of the output to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload_json FROM lineage WHERE output_hash = $1", output_hash
            )
        return [KnotLineage.model_validate_json(r["payload_json"]) for r in rows]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        """Return all lineage records that consumed ``input_hash`` as an input.

        Args:
            input_hash: Content hash of the input to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT l.payload_json FROM lineage l
                   JOIN lineage_inputs i ON l.run_id = i.run_id AND l.knot_id = i.knot_id
                   WHERE i.input_hash = $1""",
                input_hash,
            )
        return [KnotLineage.model_validate_json(r["payload_json"]) for r in rows]

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        """Return all lineage records for a specific knot across all runs.

        Args:
            knot_id: Identifier of the knot whose history is requested.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT payload_json FROM lineage WHERE knot_id = $1", knot_id)
        return [KnotLineage.model_validate_json(r["payload_json"]) for r in rows]

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        """Return all runs triggered by ``actor``.

        Args:
            actor: Actor string to filter by.

        Returns:
            List of ``RunResult`` objects, possibly empty.
        """
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT payload_json FROM runs WHERE actor = $1", actor)
        from pirn.core.run_result import RunResult

        return [RunResult.model_validate_json(r["payload_json"]) for r in rows]

    async def close(self) -> None:
        """Close the connection pool if it was created internally from a DSN."""
        await self._pool.close()
