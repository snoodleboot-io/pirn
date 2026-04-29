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
    _schema_version = 1

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
                await conn.execute(self._schema_version_ddl)
                await conn.execute(self._history_ddl)
                await self._apply_migrations(conn)
            self._initialized = True

    async def _apply_migrations(self, conn: Any) -> None:
        row = await conn.fetchrow(
            "SELECT version FROM pirn_schema_version WHERE component = $1", "history"
        )
        current = row["version"] if row else 0
        for _v in range(current, self._schema_version):
            pass  # future: _migrate_v_to_{v+1}(conn)
        await conn.execute(
            """INSERT INTO pirn_schema_version (component, version)
               VALUES ($1, $2)
               ON CONFLICT (component) DO UPDATE SET version = EXCLUDED.version""",
            "history",
            self._schema_version,
        )

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
                           ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
                           ON CONFLICT (run_id, knot_id) DO UPDATE SET
                             output_hash = EXCLUDED.output_hash,
                             outcome = EXCLUDED.outcome,
                             error_record_id = EXCLUDED.error_record_id,
                             skip_reason = EXCLUDED.skip_reason,
                             payload_json = EXCLUDED.payload_json""",
                        [
                            (
                                rec.run_id, rec.knot_id, rec.knot_class,
                                rec.knot_config_hash, rec.output_hash, rec.outcome,
                                rec.error_record_id, rec.skip_reason, rec.dispatcher,
                                rec.started_at, rec.finished_at, rec.model_dump_json(),
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
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT payload_json FROM runs WHERE run_id = $1", run_id
            )
        if row is None:
            return None
        from pirn.core.run_result import RunResult
        return RunResult.model_validate_json(row["payload_json"])

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload_json FROM lineage WHERE output_hash = $1", output_hash
            )
        return [KnotLineage.model_validate_json(r["payload_json"]) for r in rows]

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
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
        await self._ensure_init()
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT payload_json FROM lineage WHERE knot_id = $1", knot_id
            )
        return [KnotLineage.model_validate_json(r["payload_json"]) for r in rows]

    async def close(self) -> None:
        await self._pool.close()
