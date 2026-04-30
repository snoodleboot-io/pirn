from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore
from pirn.backends.sqlite._migrations import apply_migrations

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class SQLiteStore(TapestryStore):
    """TapestryStore backed by SQLite.

    Provide either an existing sqlite3.Connection or a file path; if a
    path is given the store opens its own connection lazily on first use.

    Live knot references are kept in-process; SQLite holds a snapshot of
    each knot (id, class, config, parent ids) for cross-process queries.
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
            config_json TEXT NOT NULL,
            parents_json TEXT NOT NULL,
            registered_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_knots_class ON knots(knot_class);
    """
    _schema_version = 1

    def __init__(self, *, path: str = ":memory:", connection: Any = None) -> None:
        import sqlite3

        self._path = path
        self._conn = connection or sqlite3.connect(path)
        self._live: dict[str, Knot] = {}
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._conn.executescript(self._schema_version_ddl + self._store_ddl)
        apply_migrations(self._conn, "store", self._schema_version)
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
