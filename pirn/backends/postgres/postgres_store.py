from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.postgres._lazy_pool import _LazyPool

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class PostgresStore(TapestryStore, SubscribableStore):
    """TapestryStore backed by PostgreSQL via asyncpg.

    Implements SubscribableStore via Postgres LISTEN/NOTIFY: aregister
    sends NOTIFY pirn_knots after each INSERT, and subscribe spawns a
    background task that holds a dedicated connection in LISTEN mode and
    dispatches to registered callbacks.
    """

    _schema_version_ddl = """
        CREATE TABLE IF NOT EXISTS pirn_schema_version (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL
        );
    """
    _store_ddl = """
        CREATE TABLE IF NOT EXISTS knots (
            knot_id TEXT PRIMARY KEY,
            knot_class TEXT NOT NULL,
            config_json JSONB NOT NULL,
            parents_json JSONB NOT NULL,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_knots_class ON knots(knot_class);
    """
    _schema_version = 1

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
                await conn.execute(self._schema_version_ddl)
                await conn.execute(self._store_ddl)
                await self._apply_migrations(conn)
            self._initialized = True

    async def _apply_migrations(self, conn: Any) -> None:
        row = await conn.fetchrow(
            "SELECT version FROM pirn_schema_version WHERE component = $1", "store"
        )
        current = row["version"] if row else 0
        for _v in range(current, self._schema_version):
            pass  # future: _migrate_v_to_{v+1}(conn)
        await conn.execute(
            """INSERT INTO pirn_schema_version (component, version)
               VALUES ($1, $2)
               ON CONFLICT (component) DO UPDATE SET version = EXCLUDED.version""",
            "store",
            self._schema_version,
        )

    async def aregister(self, knot: Knot) -> None:
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
            if self._subscribers:
                await conn.execute("SELECT pg_notify('pirn_knots', $1)", knot.knot_id)

    def register(self, knot: Knot) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            asyncio.run(self.aregister(knot))
        else:
            self._live[knot.knot_id] = knot
            _task = asyncio.ensure_future(self.aregister(knot))  # noqa: RUF006

    def get(self, knot_id: str) -> Knot | None:
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        return TapestrySnapshot(knot_ids=list(self._live.keys()))

    def subscribe(self, callback: Callable[[Any], None]) -> object:
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

    def _on_notify(self, conn: Any, pid: int, channel: str, payload: str) -> None:
        knot = self._live.get(payload)
        if knot is None:
            return
        for cb in list(self._subscribers.values()):
            try:
                cb(knot)
            except Exception:
                _logger.warning(
                    "PostgresStore: subscriber callback raised an exception for knot %r",
                    payload,
                    exc_info=True,
                )

    async def _listen_loop(self) -> None:
        pool = await self._pool.get()
        async with pool.acquire() as conn:
            await conn.add_listener("pirn_knots", self._on_notify)
            try:
                while self._subscribers:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                pass
            finally:
                await conn.remove_listener("pirn_knots", self._on_notify)

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None
        await self._pool.close()
